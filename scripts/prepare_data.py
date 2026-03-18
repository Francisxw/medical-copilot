"""
准备示例数据脚本
创建模拟的医疗对话和临床指南数据
"""
import json
import os
from pathlib import Path


def create_sample_conversations():
    """创建示例医患对话"""
    conversations = [
        {
            "id": "conv_001",
            "patient_info": {"age": 35, "gender": "男"},
            "conversation": [
                {"role": "doctor", "content": "你好，今天有什么不舒服？"},
                {"role": "patient", "content": "我咳嗽已经一周了，还有点发热，体温38度左右"},
                {"role": "doctor", "content": "咳嗽有痰吗？什么颜色的？"},
                {"role": "patient", "content": "有少量白痰，不太多"},
                {"role": "doctor", "content": "有胸闷气短吗？"},
                {"role": "patient", "content": "稍微有点，不太严重"},
                {"role": "doctor", "content": "以前有过类似情况吗？"},
                {"role": "patient", "content": "以前换季时偶尔会咳嗽，但这次比较严重"}
            ]
        },
        {
            "id": "conv_002",
            "patient_info": {"age": 52, "gender": "女"},
            "conversation": [
                {"role": "doctor", "content": "今天来看诊是因为什么？"},
                {"role": "patient", "content": "我最近总是觉得心慌，心跳特别快"},
                {"role": "doctor", "content": "这种情况持续多久了？"},
                {"role": "patient", "content": "大概两周了"},
                {"role": "doctor", "content": "有诱因吗？比如劳累、情绪激动？"},
                {"role": "patient", "content": "好像一活动就容易发作"},
                {"role": "doctor", "content": "有高血压、糖尿病病史吗？"},
                {"role": "patient", "content": "有高血压，吃了5年药了"}
            ]
        },
        {
            "id": "conv_003",
            "patient_info": {"age": 8, "gender": "男"},
            "conversation": [
                {"role": "doctor", "content": "小朋友哪里不舒服呀？"},
                {"role": "patient", "content": "肚子疼"},
                {"role": "doctor", "content": "哪里疼？指给叔叔看"},
                {"role": "patient", "content": "这里（指着肚脐周围）"},
                {"role": "doctor", "content": "疼了多久了？"},
                {"role": "parent", "content": "从昨天下午开始的"},
                {"role": "doctor", "content": "有发烧吗？"},
                {"role": "parent", "content": "昨天晚上有点低烧，37.5度"},
                {"role": "doctor", "content": "吃饭怎么样？有没有呕吐？"},
                {"role": "parent", "content": "不太想吃，呕吐了两次"}
            ]
        },
        {
            "id": "conv_004",
            "patient_info": {"age": 67, "gender": "男"},
            "conversation": [
                {"role": "doctor", "content": "老先生今天有什么问题？"},
                {"role": "patient", "content": "我最近总觉得喘不过气，特别是躺下的时候"},
                {"role": "doctor", "content": "这种情况多长时间了？"},
                {"role": "patient", "content": "有一个月了，最近一周越来越重"},
                {"role": "doctor", "content": "晚上睡觉需要垫高枕头吗？"},
                {"role": "patient", "content": "对，要垫两个枕头才好一点"},
                {"role": "doctor", "content": "有腿肿吗？"},
                {"role": "patient", "content": "有点，下午的时候明显"},
                {"role": "doctor", "content": "以前有心脏病吗？"},
                {"role": "patient", "content": "十年前查过冠心病"}
            ]
        }
    ]

    # 保存到文件
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "sample_conversations.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(conversations, f, ensure_ascii=False, indent=2)

    print(f"[OK] 已创建示例对话数据: {output_file}")
    return output_file


def create_sample_guidelines():
    """创建简化的临床指南数据"""
    guidelines = [
        {
            "id": "guide_001",
            "category": "呼吸系统",
            "title": "急性上呼吸道感染诊疗指南",
            "content": """
急性上呼吸道感染诊断要点：
1. 症状：咳嗽、咽痛、鼻塞、流涕，可伴发热
2. 体征：咽部充血，扁桃体可肿大
3. 病程：通常自限，7-10天
4. 检查：血常规可见淋巴细胞升高

治疗原则：
- 对症治疗：退热、止咳
- 注意休息，多饮水
- 细菌感染时可用抗生素
            """.strip(),
            "keywords": ["咳嗽", "发热", "上呼吸道感染", "感冒", "咽痛"],
            "metadata": {
                "category": "呼吸系统",
                "severity": "轻度",
                "typical_duration": "7-10天"
            }
        },
        {
            "id": "guide_002",
            "category": "心血管系统",
            "title": "心律失常诊疗指南",
            "content": """
心悸诊断流程：
1. 详细询问病史：发作诱因、持续时间、伴随症状
2. 体格检查：心率、心律、心音
3. 必要检查：心电图、24小时动态心电图、超声心动图

常见原因：
- 功能性：焦虑、疲劳、咖啡因
- 器质性：心律失常、甲亢、贫血

处理原则：
- ECG明确心律失常类型
- 针对病因治疗
- 对症处理：β受体阻滞剂等
            """.strip(),
            "keywords": ["心悸", "心慌", "心跳快", "心律失常"],
            "metadata": {
                "category": "心血管系统",
                "severity": "中度",
                "examinations": ["心电图", "Holter"]
            }
        },
        {
            "id": "guide_003",
            "category": "消化系统",
            "title": "急性腹痛诊疗指南",
            "content": """
急性腹痛鉴别诊断：
1. 腹痛部位：
   - 上腹部：胃炎、胰腺炎
   - 右上腹：胆囊炎
   - 右下腹：阑尾炎
   - 脐周：肠痉挛、早期阑尾炎

2. 伴随症状：
   - 发热：感染
   - 呕吐：梗阻、胃炎
   - 腹泻：肠炎
   - 便秘：梗阻

必需检查：
- 血常规
- 腹部超声/CT
            """.strip(),
            "keywords": ["腹痛", "肚子疼", "呕吐", "腹泻"],
            "metadata": {
                "category": "消化系统",
                "severity": "中度",
                "urgent": True
            }
        },
        {
            "id": "guide_004",
            "category": "心血管系统",
            "title": "慢性心力衰竭诊疗指南",
            "content": """
心力衰竭诊断标准：
1. 症状：
   - 呼吸困难（劳力性、端坐呼吸、夜间阵发性）
   - 乏力、水肿

2. 体征：
   - 肺部湿啰音
   - 下肢水肿
   - 颈静脉怒张

3. 检查：
   - 胸片：肺淤血
   - 超声：EF降低
   - BNP/NT-proBNP升高

治疗原则：
- 一般治疗：限盐、休息
- 药物：利尿剂、ACEI/ARB、β受体阻滞剂
- 必要时器械治疗
            """.strip(),
            "keywords": ["心衰", "心力衰竭", "喘不过气", "水肿"],
            "metadata": {
                "category": "心血管系统",
                "severity": "重度",
                "chronic": True
            }
        },
        {
            "id": "guide_005",
            "category": "通用",
            "title": "病历书写基本规范",
            "content": """
SOAP格式病历书写要求：

S (Subjective) 主诉/现病史：
- 主诉：主要症状+持续时间
- 现病史：起病情况、症状演变、伴随症状、诊治经过

O (Objective) 客观检查：
- 体格检查：生命体征、系统查体
- 辅助检查：实验室、影像学

A (Assessment) 评估：
- 初步诊断
- 鉴别诊断
- 病情严重程度

P (Plan) 计划：
- 进一步检查
- 治疗方案
- 健康指导
            """.strip(),
            "keywords": ["SOAP", "病历", "书写规范"],
            "metadata": {
                "category": "通用",
                "type": "规范"
            }
        }
    ]

    # 保存到文件
    output_dir = Path("data/guidelines")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "clinical_guidelines.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(guidelines, f, ensure_ascii=False, indent=2)

    print(f"[OK] 已创建临床指南数据: {output_file}")
    return output_file


def main():
    """主函数"""
    print("=" * 50)
    print("准备Medical Copilot示例数据")
    print("=" * 50)

    # 创建对话数据
    conv_file = create_sample_conversations()

    # 创建指南数据
    guide_file = create_sample_guidelines()

    print("\n" + "=" * 50)
    print("数据准备完成！")
    print("=" * 50)
    print(f"\n已创建文件:")
    print(f"  - {conv_file}")
    print(f"  - {guide_file}")
    print(f"\n下一步: 运行 python scripts/build_rag_index.py 构建向量索引")


if __name__ == "__main__":
    main()
