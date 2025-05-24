"""
Heti Test Runner

This script provides a unified way to run tests for the Heti project.
It can run all tests, specific test modules, or specific test cases.
"""

import subprocess
import sys
import os
import argparse

def run_tests(test_target=None, verbose=True, output_file=None):
    """
    Run the specified tests and optionally save results to a file.
    
    Args:
        test_target: The test module or test case to run. None for all tests.
        verbose: Whether to use verbose output (-v flag for pytest).
        output_file: File to save test results to. None for no file output.
    """
    # Define the base command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add verbose flag if requested
    if verbose:
        cmd.append("-v")
    
    # Add the test target if specified
    if test_target:
        cmd.append(test_target)
    
    # Create output directory if needed
    if output_file:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Run the tests
    if output_file:
        with open(output_file, "w") as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)
        print(f"Tests completed with exit code: {result.returncode}")
        print(f"Results saved to {output_file}")
    else:
        result = subprocess.run(cmd)
    
    return result.returncode

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Heti tests")
    parser.add_argument("--target", help="Test module or case to run (e.g., 'tests/test_memory_monitor.py')")
    parser.add_argument("--quiet", action="store_true", help="Run tests without verbose output")
    parser.add_argument("--output", help="Save test results to the specified file")
    parser.add_argument("--memory-monitor", action="store_true", help="Run only Memory Monitor tests")
    parser.add_argument("--api-client", action="store_true", help="Run only OpenMemory client tests")
    
    args = parser.parse_args()
    
    # Determine the test target
    test_target = args.target
    if args.memory_monitor:
        test_target = "tests/test_memory_monitor.py"
    elif args.api_client:
        test_target = "tests/test_openmemory_client.py"
    
    # Run the tests
    exit_code = run_tests(
        test_target=test_target,
        verbose=not args.quiet,
        output_file=args.output
    )
    
    # Exit with the same code as pytest
    sys.exit(exit_code) 