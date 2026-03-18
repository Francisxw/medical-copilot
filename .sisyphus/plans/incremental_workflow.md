# Phase 2: Incremental Workflow Implementation Plan

## TL;DR

> **Quick Summary**: Add LangGraph checkpoint support with SQLite storage to enable incremental workflow processing for the medical copilot. This allows real-time state updates and session resumption.

> **Deliverables**:
> - LangGraph checkpoint with SQLite persistence
> - New incremental API endpoints (/api/session/*)
> - Updated workflow to support step-by-step execution
> - Frontend polling mechanism for real-time updates

> **Estimated Effort**: Medium (4-6 hours)
> **Parallel Execution**: NO - Sequential (tasks depend on each other)
> **Critical Path**: Checkpoint setup → Workflow modifications → API endpoints → Frontend integration

---

## Context

### Original Request
User wants to implement Phase 2 of the voice integration plan: **Incremental Workflow** with checkpoint support.

### Current State
- **Backend**: FastAPI + LangGraph
- **Workflow**: Batch-only processing via `POST /api/generate-emr`
- **Checkpoint**: NOT implemented
- **Session**: No persistent session state between requests

### Requirements Confirmed
- **Checkpoint Storage**: Local File (SQLite)
- **Voice Integration**: Skip for now
- **Test Strategy**: Tests After

---

## Work Objectives

### Core Objective
Enable incremental workflow processing with checkpoint persistence:
1. Save workflow state after each step
2. Allow session resumption
3. Support real-time progress updates

### Concrete Deliverables
1. **Checkpoint Setup**: Add `langgraph-checkpoint` dependency, configure SQLite persistence
2. **Modified Workflow**: Update `workflow.py` to support checkpoint-aware execution
3. **New API Endpoints**:
   - `POST /api/session/start` - Initialize session with checkpoint
   - `POST /api/session/{session_id}/message` - Add message, process next step
   - `GET /api/session/{session_id}/status` - Get current state and progress
   - `DELETE /api/session/{session_id}` - Clean up session
4. **Frontend Integration**: Update Streamlit to poll for incremental updates

### Definition of Done
- [ ] New session can be created and state persisted to SQLite
- [ ] Adding a message triggers only the necessary workflow steps
- [ ] Previous steps are not re-executed (checkpoint resume)
- [ ] Frontend shows real-time progress as steps complete
- [ ] Session can be resumed after interruption

### Must Have
- Checkpoint persistence survives server restart
- Proper error handling when checkpoint not found
- Clean session cleanup mechanism

### Must NOT Have (Guardrails)
- Don't change existing `/api/generate-emr` endpoint (backward compatibility)
- Don't add WebSocket (not compatible with Streamlit polling pattern)
- Don't change session_state key names

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: Tests After
- **Framework**: pytest

### QA Policy
Every task includes agent-executed QA scenarios:
- **Backend API**: Use Bash (curl) — Send requests, assert status + response fields
- **Integration**: Use Bash — Run full workflow, verify checkpoint persistence

---

## Execution Strategy

### Task Sequence (Sequential)

**Wave 1: Foundation**
- Task 1: Add langgraph-checkpoint dependency
- Task 2: Create checkpoint manager module
- Task 3: Configure SQLite checkpoint storage

**Wave 2: Workflow Modifications**
- Task 4: Update workflow.py to support checkpoint
- Task 5: Add session management utilities
- Task 6: Test checkpoint persistence locally

**Wave 3: API Endpoints**
- Task 7: Create session routes module
- Task 8: Implement /api/session/start
- Task 9: Implement /api/session/{id}/message
- Task 10: Implement /api/session/{id}/status
- Task 11: Implement /api/session/{id} cleanup

**Wave 4: Frontend Integration**
- Task 12: Add Streamlit polling mechanism
- Task 13: Update frontend to use incremental API
- Task 14: Test end-to-end flow

---

## TODOs

### Wave 1: Foundation

- [ ] 1. Add langgraph-checkpoint dependency

  **What to do**:
  - Add `langgraph-checkpoint` to requirements.txt
  - Install package: `pip install langgraph-checkpoint`
  - Verify installation: `python -c "from langgraph.checkpoint import SqlSaver; print('OK')"`

  **Must NOT do**:
  - Don't modify other dependencies

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple dependency addition
  - **Skills**: []
  - **Skills Evaluated but Omitted**: None

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Tasks 2-14
  - **Blocked By**: None

  **References**:
  - `requirements.txt` - Current dependencies
  - LangGraph checkpoint docs: `https://langchain-ai.github.io/langgraph/concepts/checkpointing/`

  **Acceptance Criteria**:
  - [ ] Package installed successfully
  - [ ] Import works without errors

  **QA Scenarios**:
  ```
  Scenario: Verify langgraph-checkpoint installed
    Tool: Bash
    Preconditions: requirements.txt updated
    Steps:
      1. Run: pip install langgraph-checkpoint
      2. Run: python -c "from langgraph.checkpoint import SqlSaver; print('OK')"
    Expected Result: Prints "OK" without errors
    Evidence: .sisyphus/evidence/task-1-install.txt
  ```

  **Commit**: NO

- [ ] 2. Create checkpoint manager module

  **What to do**:
  - Create `src/checkpoint/__init__.py`
  - Create `src/checkpoint/manager.py` with:
    - `CheckpointManager` class
    - SQLite configuration
    - Methods: `get_config()`, `create_thread()`, `get_thread()`

  **Must NOT do**:
  - Don't modify existing workflow logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Module creation with standard patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 3-14
  - **Blocked By**: Task 1

  **References**:
  - `src/graph/workflow.py` - Current workflow structure
  - LangGraph checkpoint docs

  **Acceptance Criteria**:
  - [ ] Module created at src/checkpoint/manager.py
  - [ ] CheckpointManager class implemented

  **QA Scenarios**:
  ```
  Scenario: Verify checkpoint module structure
    Tool: Bash
    Preconditions: Module created
    Steps:
      1. Run: python -c "from src.checkpoint.manager import CheckpointManager; print('OK')"
    Expected Result: No import errors
    Evidence: .sisyphus/evidence/task-2-import.txt
  ```

  **Commit**: NO

- [ ] 3. Configure SQLite checkpoint storage

  **What to do**:
  - Update `src/checkpoint/manager.py` to configure SQLite storage
  - Set up database path: `./data/checkpoints/checkpoints.db`
  - Create directory if not exists

  **Must NOT do**:
  - Don't create tables manually (LangGraph handles this)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Configuration task
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 4-14
  - **Blocked By**: Task 2

  **Acceptance Criteria**:
  - [ ] SQLite config created
  - [ ] Directory ./data/checkpoints/ exists or created

  **Commit**: NO

### Wave 2: Workflow Modifications

- [ ] 4. Update workflow.py to support checkpoint

  **What to do**:
  - Modify `src/graph/workflow.py`:
    - Import checkpoint components
    - Add `checkpoint_config` parameter to workflow
    - Update `_build_graph()` to include checkpointer
    - Modify `run()` to accept thread_id for resumption

  **Must NOT do**:
  - Don't break existing batch `run()` method (backward compatibility)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Core LangGraph modification, requires careful integration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 5-14
  - **Blocked By**: Task 3

  **References**:
  - `src/graph/workflow.py` - Current implementation
  - LangGraph checkpoint API

  **Acceptance Criteria**:
  - [ ] Workflow can be compiled with checkpointer
  - [ ] Existing batch run() still works

  **QA Scenarios**:
  ```
  Scenario: Test workflow with checkpoint
    Tool: Bash
    Preconditions: Workflow updated
    Steps:
      1. Run: python -c "
import asyncio
from src.graph.workflow import MedicalCopilotWorkflow

async def test():
    wf = MedicalCopilotWorkflow()
    # Check if graph has checkpointer attribute
    print('Has checkpointer:', hasattr(wf.graph, 'checkpointer'))
    print('OK')

asyncio.run(test())
"
    Expected Result: Prints "Has checkpointer: True"
    Evidence: .sisyphus/evidence/task-4-checkpoint.txt
  ```

  **Commit**: NO

- [ ] 5. Add session management utilities

  **What to do**:
  - Create `src/session/manager.py`:
    - `SessionManager` class
    - Create new session
    - Get session state
    - List active sessions
    - Delete session

  **Must NOT do**:
  - Don't implement API routes yet (Task 7)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Utility module creation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 6-14
  - **Blocked By**: Task 4

  **Acceptance Criteria**:
  - [ ] SessionManager class created
  - [ ] Can create/get/delete sessions

  **Commit**: NO

- [ ] 6. Test checkpoint persistence locally

  **What to do**:
  - Write test script to verify checkpoint works:
    - Create workflow with checkpoint
    - Run partial workflow
    - Get checkpoint state
    - Resume workflow from checkpoint

  **Must NOT do**:
  - Don't modify production code

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Verification script
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 7-14
  - **Blocked By**: Task 5

  **Acceptance Criteria**:
  - [ ] Checkpoint can be saved
  - [ ] Checkpoint can be resumed

  **Commit**: NO

### Wave 3: API Endpoints

- [ ] 7. Create session routes module

  **What to do**:
  - Create `src/api/session_routes.py`:
    - New router for session endpoints
    - Import SessionManager
    - Set up dependency injection

  **Must NOT do**:
  - Don't modify existing routes.py

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Module creation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 8-11
  - **Blocked By**: Task 6

  **Acceptance Criteria**:
  - [ ] Router created with /api/session prefix

  **Commit**: NO

- [ ] 8. Implement /api/session/start

  **What to do**:
  - Add endpoint `POST /api/session/start`:
    - Accept patient_info (optional)
    - Create new session with thread_id
    - Return session_id, thread_id, initial state

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: API implementation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 9-14
  - **Blocked By**: Task 7

  **Acceptance Criteria**:
  - [ ] Endpoint returns valid session_id
  - [ ] State persisted to SQLite

  **QA Scenarios**:
  ```
  Scenario: Test session start endpoint
    Tool: Bash
    Preconditions: Server running
    Steps:
      1. Run: curl -X POST http://localhost:8000/api/session/start -H "Content-Type: application/json" -d '{"patient_info": {"age": 30, "gender": "男"}}'
    Expected Result: Returns session_id and thread_id
    Evidence: .sisyphus/evidence/task-8-start.json
  ```

  **Commit**: NO

- [ ] 9. Implement /api/session/{id}/message

  **What to do**:
  - Add endpoint `POST /api/session/{session_id}/message`:
    - Accept message (role, content)
    - Get current checkpoint state
    - Resume workflow from checkpoint
    - Return updated state and completed steps

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Core incremental processing logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 10-14
  - **Blocked By**: Task 8

  **Acceptance Criteria**:
  - [ ] Message added to conversation
  - [ ] Workflow processes incrementally
  - [ ] Previous steps not re-executed

  **Commit**: NO

- [ ] 10. Implement /api/session/{id}/status

  **What to do**:
  - Add endpoint `GET /api/session/{session_id}/status`:
    - Return current conversation
    - Return current workflow state
    - Return completed steps
    - Return current node (e.g., "extract_info", "generate_emr")

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple GET endpoint
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 11-14
  - **Blocked By**: Task 9

  **Acceptance Criteria**:
  - [ ] Returns current state
  - [ ] Returns progress info

  **Commit**: NO

- [ ] 11. Implement /api/session/{id} cleanup

  **What to do**:
  - Add endpoint `DELETE /api/session/{session_id}`:
    - Delete checkpoint data
    - Clean up session resources
    - Return confirmation

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple DELETE endpoint
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 12-14
  - **Blocked By**: Task 10

  **Acceptance Criteria**:
  - [ ] Session deleted successfully
  - [ ] Checkpoint data removed

  **Commit**: NO

### Wave 4: Frontend Integration

- [ ] 12. Add Streamlit polling mechanism

  **What to do**:
  - Modify `frontend/app.py`:
    - Add polling function for status updates
    - Add auto-refresh toggle
    - Show progress indicator

  **Must NOT do**:
  - Don't change existing widget keys

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Frontend integration with state management
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 13-14
  - **Blocked By**: Task 11

  **Acceptance Criteria**:
  - [ ] Polling function implemented
  - [ ] Progress indicator visible

  **Commit**: NO

- [ ] 13. Update frontend to use incremental API

  **What to do**:
  - Modify frontend/app.py:
    - Change from single /api/generate-emr call
    - Use /api/session/start → message loop → status polling
    - Display incremental results

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Frontend-backend integration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 14
  - **Blocked By**: Task 12

  **Acceptance Criteria**:
  - [ ] Frontend calls new API endpoints
  - [ ] Results display incrementally

  **Commit**: NO

- [ ] 14. Test end-to-end flow

  **What to do**:
  - Start backend server
  - Start Streamlit frontend
  - Create session
  - Add messages incrementally
  - Verify checkpoint persistence
  - Test session resumption

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration testing
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocked By**: Task 13

  **Acceptance Criteria**:
  - [ ] Full flow works
  - [ ] Checkpoint persists across restarts

  **QA Scenarios**:
  ```
  Scenario: End-to-end incremental workflow
    Tool: Bash
    Preconditions: Both servers running
    Steps:
      1. Create session: curl -X POST http://localhost:8000/api/session/start
      2. Add message: curl -X POST http://localhost:8000/api/session/{id}/message -d '{"role": "patient", "content": "我咳嗽一周了"}'
      3. Check status: curl http://localhost:8000/api/session/{id}/status
      4. Verify conversation contains message
    Expected Result: All steps successful
    Evidence: .sisyphus/evidence/task-14-e2e.json
  ```

  **Commit**: NO

---

## Final Verification Wave

> After ALL implementation tasks, run verification.

- [ ] F1. **API Contract Verification**

  Verify all new endpoints respond correctly:
  - POST /api/session/start → 200 + session_id
  - POST /api/session/{id}/message → 200 + state
  - GET /api/session/{id}/status → 200 + progress
  - DELETE /api/session/{id} → 200 + confirmation

- [ ] F2. **Checkpoint Persistence**

  - Create session, add message
  - Restart server
  - Resume session - verify state restored

- [ ] F3. **Backward Compatibility**

  - Existing /api/generate-emr still works

---

## Success Criteria

### Verification Commands
```bash
# Test new endpoints
curl -X POST http://localhost:8000/api/session/start -H "Content-Type: application/json" -d '{"patient_info": {"age": 30, "gender": "男"}}'

# Test session message
curl -X POST http://localhost:8000/api/session/{session_id}/message -H "Content-Type: application/json" -d '{"role": "patient", "content": "我咳嗽一周了"}'

# Test status
curl http://localhost:8000/api/session/{session_id}/status
```

### Final Checklist
- [ ] New session endpoints work
- [ ] Checkpoint persists to SQLite
- [ ] Incremental processing works (not re-running completed steps)
- [ ] Frontend shows real-time progress
- [ ] Old API still works (backward compatible)
