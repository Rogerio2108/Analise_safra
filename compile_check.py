"""
Script de verificação de compilação Python.
Verifica se todos os arquivos .py do projeto compilam sem erros de sintaxe.
"""

import py_compile
import os
import sys
from pathlib import Path

def check_compile(file_path):
    """
    Tenta compilar um arquivo Python e retorna True se sucesso, False caso contrário.
    """
    try:
        py_compile.compile(file_path, doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        return False, str(e)

def find_py_files(root_dir="."):
    """
    Encontra todos os arquivos .py no diretório raiz e subdiretórios.
    Ignora diretórios como __pycache__, .git, venv, etc.
    """
    py_files = []
    root_path = Path(root_dir)
    
    ignore_dirs = {'__pycache__', '.git', 'venv', 'env', '.venv', 'node_modules'}
    
    for py_file in root_path.rglob("*.py"):
        # Verifica se algum diretório pai está na lista de ignorados
        if not any(part in ignore_dirs for part in py_file.parts):
            py_files.append(py_file)
    
    return sorted(py_files)

def main():
    """
    Função principal: verifica compilação de todos os arquivos .py.
    """
    print("=" * 70)
    print("VERIFICAÇÃO DE COMPILAÇÃO PYTHON")
    print("=" * 70)
    print()
    
    py_files = find_py_files()
    
    if not py_files:
        print("❌ Nenhum arquivo .py encontrado!")
        sys.exit(1)
    
    print(f"Encontrados {len(py_files)} arquivo(s) .py:")
    print()
    
    errors = []
    success_count = 0
    
    for py_file in py_files:
        rel_path = py_file.relative_to(Path("."))
        success, error_msg = check_compile(str(py_file))
        
        if success:
            print(f"✅ {rel_path}")
            success_count += 1
        else:
            print(f"❌ {rel_path}")
            print(f"   Erro: {error_msg}")
            errors.append((rel_path, error_msg))
    
    print()
    print("=" * 70)
    print(f"RESUMO: {success_count}/{len(py_files)} arquivo(s) compilaram com sucesso")
    print("=" * 70)
    
    if errors:
        print()
        print("❌ ERROS ENCONTRADOS:")
        for file_path, error_msg in errors:
            print(f"  - {file_path}: {error_msg}")
        sys.exit(1)
    else:
        print()
        print("✅ OK: all .py files compile")
        sys.exit(0)

if __name__ == "__main__":
    main()

