import uuid

import pytest
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from agent0.core.types import RunStatus, Task
from agent0.orchestrator.steps import Engine
from agent0.orchestrator.temporal import Activities, RunInput, RunWorkflow
from tests.orchestrator.test_engine_e2e import runtime  # noqa: F401

pytestmark = pytest.mark.integration


async def test_workflow_runs_task_durably(runtime):  # noqa: F811
    async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
        acts = Activities(Engine(runtime))
        async with Worker(
            env.client,
            task_queue="t",
            workflows=[RunWorkflow],
            activities=acts.all(),
        ):
            outcome = await env.client.execute_workflow(
                RunWorkflow.run,
                RunInput(task=Task(title="hello", prompt="write hello.txt"), run_id="r1"),
                id=str(uuid.uuid4()),
                task_queue="t",
            )
    assert outcome.status == RunStatus.SUCCEEDED
