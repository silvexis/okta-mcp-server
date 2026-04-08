"""Concurrency utilities for parallel test execution."""

import asyncio
from typing import List, Callable, Any, TypeVar

T = TypeVar('T')


async def run_with_concurrency(
    tasks: List[Callable[[], Any]],
    max_concurrency: int
) -> List[Any]:
    """
    Run tasks concurrently with controlled concurrency limit.

    Uses asyncio.Semaphore to limit concurrent execution and asyncio.gather
    to run all tasks. Results are returned in the same order as tasks,
    with exceptions preserved.

    Args:
        tasks: List of async callable functions (no arguments)
        max_concurrency: Maximum number of tasks to run concurrently

    Returns:
        List of results in original order (exceptions preserved)

    Example:
        tasks = [
            lambda: fetch_data(id=1),
            lambda: fetch_data(id=2),
            lambda: fetch_data(id=3),
        ]
        results = await run_with_concurrency(tasks, max_concurrency=2)
    """
    if not tasks:
        return []

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run_with_semaphore(task: Callable[[], Any]) -> Any:
        """Execute task with semaphore control."""
        async with semaphore:
            return await task()

    # Run all tasks concurrently with semaphore control
    # return_exceptions=True preserves exceptions in result list
    results = await asyncio.gather(
        *[run_with_semaphore(task) for task in tasks],
        return_exceptions=True
    )

    return results
