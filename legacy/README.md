# Legacy code

`legacy/python` contains the archived Streamlit implementation of Portico.
It is historical reference material, not an active product path.

The active application is the C# code in `src/Portico.*`. Do not add features,
fixes, CI jobs, deployment work, or new dependencies to the archived Python
app unless a separate decision restores it as an active product.

The C# demo still uses `demo/data` at the repository root. That shared,
synthetic fixture remains outside this archive so the current .NET `doctor`
command continues to work.
