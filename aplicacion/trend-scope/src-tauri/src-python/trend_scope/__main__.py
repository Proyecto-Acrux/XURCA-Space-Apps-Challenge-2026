from pytauri import Builder, Context, Commands
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from trend_scope.handlers.analysis import run_regression_analysis

# 1. Instanciamos el registro de comandos de PyTauri
commands = Commands()

# 2. Esquema de validación con Pydantic para el payload que llega desde la UI
class RegressionPayload(BaseModel):
    algorithm: str
    x: List[float]
    y: List[float]
    options: Optional[Dict[str, Any]] = None

# 3. Decoramos la función para exponerla como comando de Tauri
@commands.command()
def execute_regression(payload: RegressionPayload) -> Dict[str, Any]:
    try:
        result = run_regression_analysis(
            algorithm=payload.algorithm,
            x=payload.x,
            y=payload.y,
            options=payload.options
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 4. Función main que levanta la app conectando los comandos
def main() -> int:
    context = Context()

    app = (
        Builder(context)
        .invoke_handler(commands)  # Inyectamos el router de comandos
        .build()
    )

    app.run()
    return 0
