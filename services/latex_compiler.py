import subprocess
import os


def compile_latex(tex_content: str, output_name: str, output_dir: str = "outputs"):
    os.makedirs(output_dir, exist_ok=True)

    tex_path = os.path.join(output_dir, f"{output_name}.tex")

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", tex_path],
        cwd=output_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return os.path.join(output_dir, f"{output_name}.pdf")
