#!/usr/bin/env python3
"""
██████╗░██████╗░███████╗██████╗░░██████╗███████╗░█████╗░██████╗░░█████╗░██╗░░██╗
██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║░░██║
██║░░██║██████╔╝█████╗░░██████╔╝╚█████╗░█████╗░░███████║██████╔╝██║░░╚═╝███████║
██║░░██║██╔═══╝░██╔══╝░░██╔═══╝░░╚═══██╗██╔══╝░░██╔══██║██╔══██╗██║░░██╗██╔══██║
██████╔╝██║░░░░░███████╗██║░░░░░██████╔╝███████╗██║░░██║██║░░██║╚█████╔╝██║░░██║
╚═════╝░╚═╝░░░░░╚══════╝╚═╝░░░░░╚═════╝░╚══════╝╚═╝░░╚═╝╚═╝░░╚═╝░╚════╝░╚═╝░░╚═╝

RootSearch Engine — Autonomous Deep Testing & Benchmarking Harness
Executes 500+ Parameterized Assertions & Micro-Performance SLAs
"""

import sys
import os
import time
import subprocess
from colorama import Fore, Style, init

init(autoreset=True)

def print_header():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}" + "="*80)
    print(f"{Fore.CYAN}{Style.BRIGHT}  ROOTSEARCH AI ENGINE — AUTONOMOUS DEEP TEST SUITE & BENCHMARK HARNESS")
    print(f"{Fore.CYAN}{Style.BRIGHT}" + "="*80)
    print(f"{Fore.YELLOW}Targeting 500+ Parameterized Assertions Across 6 Core Refactored Modules\n")

def run_suite():
    print_header()
    
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_sources_and_aggregator.py",
        "tests/test_fetching_engine.py",
        "tests/test_rag_pipeline.py",
        "tests/test_cognitive_synthesis.py",
        "tests/test_security_fuzzing.py",
        "tests/test_benchmarks.py",
        "-v",
        "--tb=short"
    ]
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=False)
    duration = time.time() - start_time
    
    print("\n" + Fore.CYAN + "="*80)
    if result.returncode == 0:
        print(f"{Fore.GREEN}{Style.BRIGHT}SUCCESS: ALL DEEP TEST SUITE SUITES & BENCHMARKS PASSED PERFECTLY!")
    else:
        print(f"{Fore.RED}{Style.BRIGHT}FAILURE: SOME TEST SUITES ENCOUNTERED ERRORS (Exit code: {result.returncode})")
    print(f"{Fore.CYAN}Total Execution Duration: {duration:.2f} seconds")
    print(Fore.CYAN + "="*80 + "\n")
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_suite())
