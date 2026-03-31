"""
LangGraph主工作流编排
将多个Agent串联成完整的病历生成流程

注意：检索策略通过外部注入，工作流本身只负责编排
"""

from langgraph.graph import StateGraph, END
from typing import Any, Dict, Optional
from loguru import logger
import uuid
from datetime import datetime

from src.graph.state import GraphState
from src.agents.dialogue_agent import DialogueAgent
from src.agents.generation_agent import GenerationAgent
from src.agents.qa_agent import QAAgent
from src.agents.revision_agent import RevisionAgent
from src.config import get_settings
from src.models.function_schemas import MedicalInfoExtraction
from src.retrieval.factory import create_retrieval_strategy

settings = get_settings()


class MedicalCopilotWorkflow:
    """
    医疗Copilot工作流
    使用LangGraph编排多Agent协作

    检索策略通过构造函数注入，默认使用 factory 创建
    """

    def __init__(
        self,
        retrieval_mode: Optional[str] = None,
        use_vector_retrieval: bool = False,
        retrieval_agent: Optional[Any] = None,  # 新增：支持外部注入
    ):
        # 初始化各Agent
        self.dialogue_agent = DialogueAgent()

        # 使用外部注入的 retrieval agent，或通过 factory 创建
        if retrieval_agent is not None:
            self.retrieval_agent = retrieval_agent
            # 从注入的 agent 推断模式
            self.retrieval_mode = getattr(
                retrieval_agent, "mode", retrieval_mode or settings.retrieval_mode
            )
            logger.info(f"✅ 使用外部注入的检索策略")
        else:
            # 通过 factory 创建检索策略（保留向后兼容）
            mode = retrieval_mode or settings.retrieval_mode
            if use_vector_retrieval:
                mode = "vector"

            # 根据模式创建不同的配置参数
            extra_kwargs = {}
            if mode == "llamaindex":
                extra_kwargs = {
                    "collection_name": settings.llamaindex_collection_name,
                    "persist_dir": settings.llamaindex_persist_dir,
                }

            self.retrieval_agent = create_retrieval_strategy(mode, **extra_kwargs)
            self.retrieval_mode = mode
            logger.info(f"✅ 使用检索模式: {mode}")

        self.generation_agent = GenerationAgent()
        self.qa_agent = QAAgent()
        self.revision_agent = RevisionAgent()

        # 构建工作流图
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """构建LangGraph工作流"""

        # 创建状态图
        workflow = StateGraph(GraphState)

        # 添加节点（每个Agent作为一个节点）
        workflow.add_node("extract_info", self._extract_info_node)
        workflow.add_node("retrieve_knowledge", self._retrieve_knowledge_node)
        workflow.add_node("generate_emr", self._generate_emr_node)
        workflow.add_node("qa_check", self._qa_check_node)
        workflow.add_node("revise_emr", self._revise_emr_node)

        # 设置入口
        workflow.set_entry_point("extract_info")

        # 添加边（定义执行流程）
        workflow.add_edge("extract_info", "retrieve_knowledge")
        workflow.add_edge("retrieve_knowledge", "generate_emr")
        workflow.add_edge("generate_emr", "qa_check")

        # 添加条件边（根据质控结果决定是否修改）
        workflow.add_conditional_edges(
            "qa_check", self._should_revise, {"revise": "revise_emr", "end": END}
        )

        # 修改后再次质控
        workflow.add_edge("revise_emr", "qa_check")

        return workflow.compile()

    async def _extract_info_node(self, state: GraphState) -> GraphState:
        """节点1: 提取医疗信息"""
        logger.info("=== Agent 1: 对话解析 ===")

        conversation = state.get("conversation", [])
        extracted_info = await self.dialogue_agent.extract(conversation)

        state["extracted_info"] = extracted_info
        state["error_message"] = None

        return state

    async def _retrieve_knowledge_node(self, state: GraphState) -> GraphState:
        """节点2: 检索临床指南"""
        logger.info("=== Agent 2: 知识检索 ===")

        extracted_info = state["extracted_info"]
        symptoms = extracted_info.symptoms or []

        if symptoms:
            guidelines = await self.retrieval_agent.retrieve_by_symptoms(symptoms)
        else:
            guidelines = []

        state["retrieved_guidelines"] = guidelines

        return state

    async def _generate_emr_node(self, state: GraphState) -> GraphState:
        """节点3: 生成病历"""
        logger.info("=== Agent 3: 病历生成 ===")

        patient_info_raw = state.get("patient_info", {})
        medical_info = state["extracted_info"]
        guidelines = state.get("retrieved_guidelines", [])

        draft_emr = await self.generation_agent.generate(
            patient_info_raw,
            medical_info,
            guidelines,
        )

        state["draft_emr"] = draft_emr

        return state

    async def _qa_check_node(self, state: GraphState) -> GraphState:
        """节点4: 质控检查"""
        logger.info("=== Agent 4: 质控检查 ===")

        draft_emr = state.get("draft_emr")
        medical_info = state["extracted_info"]

        if draft_emr is None:
            raise ValueError("draft_emr 为空，无法进行质控检查")

        qa_report = await self.qa_agent.check(draft_emr, medical_info)

        state["qa_report"] = qa_report
        state["final_emr"] = draft_emr  # 默认使用草稿作为最终版本

        # 根据质控结果决定是否需要修改
        state["needs_revision"] = not qa_report.is_complete

        state["iteration_count"] = state.get("iteration_count", 0) + 1

        return state

    async def _revise_emr_node(self, state: GraphState) -> GraphState:
        """节点5: 修改病历（根据质控问题调用 RevisionAgent）"""
        logger.info("=== Agent 5: 病历修改 ===")

        qa_report = state.get("qa_report")
        draft_emr = state.get("draft_emr")
        medical_info = state["extracted_info"]

        if qa_report is None:
            logger.warning("qa_report 为空，跳过修改")
            state["needs_revision"] = False
            return state

        issues = qa_report.issues or []
        if not issues:
            logger.info("无质控问题，跳过修改")
            state["needs_revision"] = False
            return state

        logger.info(f"检测到 {len(issues)} 个质控问题，开始修改病历")

        if draft_emr is None:
            logger.warning("draft_emr 为空，跳过修改")
            state["needs_revision"] = False
            return state

        try:
            revised_emr = await self.revision_agent.revise(
                original_emr=draft_emr,
                qa_report=qa_report,
                medical_info=medical_info,
            )
            state["draft_emr"] = revised_emr
            state["final_emr"] = revised_emr
            logger.info("[OK] 病历修改完成")
        except Exception as e:
            logger.error(f"病历修改失败: {e}", exc_info=True)
            # 保留当前版本，安全退出修订循环
            state["final_emr"] = draft_emr

        # 无论成功或失败，结束修订循环
        state["needs_revision"] = False

        return state

    def _should_revise(self, state: GraphState) -> str:
        """条件判断：是否需要修改病历"""
        needs_revision = state.get("needs_revision", False)
        iteration_count = state.get("iteration_count", 0)
        max_iterations = settings.max_revision_iterations

        if needs_revision and iteration_count < max_iterations:
            logger.info(f"质控未通过，进行第 {iteration_count} 次修改")
            return "revise"
        else:
            if needs_revision:
                logger.warning(f"达到最大修改次数 ({max_iterations})，强制完成")
            else:
                logger.info("质控通过，生成完成")
            return "end"

    async def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行完整工作流

        Args:
            inputs: 输入数据，包含conversation和patient_info

        Returns:
            完整的处理结果
        """
        # 初始化状态
        initial_state: GraphState = {
            "conversation": inputs.get("conversation", []),
            "patient_info": inputs.get("patient_info", {}),
            "extracted_info": MedicalInfoExtraction(),
            "retrieved_guidelines": [],
            "draft_emr": None,
            "final_emr": None,
            "qa_report": None,
            "iteration_count": 0,
            "needs_revision": False,
            "error_message": None,
            "timestamp": datetime.now().isoformat(),
            "session_id": str(uuid.uuid4()),
        }

        logger.info(f"开始处理会话: {initial_state['session_id']}")

        # Let unexpected exceptions propagate — the global exception handler
        # in main.py will log them and return a sanitized response.
        final_state = await self.graph.ainvoke(initial_state)  # type: ignore

        # 提取结果（统一转换为可序列化字典）
        extracted_info = final_state["extracted_info"].model_dump(mode="json")
        final_emr = final_state["final_emr"]
        qa_report = final_state["qa_report"]

        if final_emr is not None:
            final_emr = final_emr.model_dump(mode="json")
        if qa_report is not None:
            qa_report = qa_report.model_dump(mode="json")

        result = {
            "session_id": final_state["session_id"],
            "timestamp": final_state["timestamp"],
            "patient_info": final_state["patient_info"],
            "extracted_info": extracted_info,
            "final_emr": final_emr,
            "qa_report": qa_report,
            "iteration_count": final_state["iteration_count"],
            "error_message": final_state["error_message"],
        }

        logger.info("工作流执行完成")
        return result
