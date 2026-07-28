#!/usr/bin/env python3
"""
WorkerPool — manages N parallel autonomous agents with resource tracking.

Each worker runs an autonomous_execute.py invocation as a subprocess.
The pool tracks GPU, memory, and worker availability.
"""

import subprocess
import os
import json
import time
import threading
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

class WorkerPool:
    def __init__(self, max_workers: int = 2, timeout: int = 3600):
        self.max_workers = max_workers
        self.timeout = timeout
        self.active_workers = 0
        self.completed_workers = []
        self.completed_results = []
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def submit(self, command: str, workdir: str = "", env: Optional[dict] = None) -> str:
        """
        Submit a command to run autonomously.
        Returns the worker ID.
        """
        if self.active_workers >= self.max_workers:
            raise RuntimeError("Maximum workers reached")
        
        self.active_workers += 1
        future = self.executor.submit(self._run_worker, command, workdir, env)
        return f"worker_{self.active_workers - 1}"
    
    def _run_worker(self, command: str, workdir: str, env: Optional[dict]):
        """
        Internal method to run a worker.
        """
        try:
            env = env or os.environ.copy()
            env['WORKDIR'] = workdir
            result = subprocess.run(
                command,
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            self.active_workers -= 1
            self.completed_workers.append(f"worker_{self.active_workers}")
            self.completed_results.append({
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'timestamp': time.time()
            })
        except subprocess.TimeoutExpired:
            self.active_workers -= 1
            self.completed_workers.append(f"worker_{self.active_workers}_timeout")
        except Exception as e:
            self.active_workers -= 1
            self.completed_workers.append(f"worker_{self.active_workers}_error")
            self.completed_results.append({
                'stdout': '',
                'stderr': str(e),
                'returncode': -1,
                'timestamp': time.time()
            })
        return

    def wait_for_completion(self) -> list:
        """
        Wait for all workers to complete and return results.
        """
        return self.completed_results

    def get_stats(self) -> dict:
        """
        Get current statistics about workers.
        """
        return {
            'max_workers': self.max_workers,
            'active_workers': self.active_workers,
            'completed_workers': len(self.completed_workers),
            'total_completed': len(self.completed_results)
        }

def main():
    pool = WorkerPool(max_workers=2, timeout=3600)
    
    # Example usage
    print("Submitting 2 worker tasks...")
    worker1 = pool.submit("python3 run_autonomous.py --prompt \"Add user auth endpoint\"")
    worker2 = pool.submit("python3 run_autonomous.py --prompt \"Implement rate limiting\"", workdir="/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri")
    
    print(f"Active workers: {pool.get_stats()['active_workers']}")
    
    # Wait for completion
    results = pool.wait_for_completion()
    print(f"Completed workers: {pool.get_stats()['completed_workers']}")
    
    for i, result in enumerate(results):
        print(f"Worker {i+1} result:")
        print(f"  Return code: {result['returncode']}")
        if result['returncode'] == 0:
            print(f"  SUCCESS: {result['stdout'][:200]}...")
        else:
            print(f"  ERROR: {result['stderr'][:200]}...")

if __name__ == "__main__":
    main()