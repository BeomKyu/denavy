import time
import ast
from denavy.rc2_autoregressive_bias.ast_parser import ASTCodeAnalyzer

def benchmark():
    analyzer = ASTCodeAnalyzer()

    # Create a reasonably large piece of code
    code = "\n".join([f"def func_{i}():\n    print({i})" for i in range(1000)])

    iterations = 100

    print(f"Benchmarking {iterations} iterations of AST analysis...")

    # Warm up
    analyzer.analyze(code)

    start_time = time.perf_counter()
    for _ in range(iterations):
        analyzer.analyze(code)
    end_time = time.perf_counter()

    total_time = end_time - start_time
    avg_time = total_time / iterations

    print(f"Total time: {total_time:.4f}s")
    print(f"Average time per iteration: {avg_time:.6f}s")

if __name__ == "__main__":
    benchmark()
