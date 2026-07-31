import os
import ast


BASE_DIR = r"E:\Projcets\odoo17\odoo\custom_addons"


def check_python_syntax(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            ast.parse(f.read())

        return None

    except SyntaxError as e:
        return f"SyntaxError line {e.lineno}: {e.msg}"


def check_controller(path):

    problems = []

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # import checks
    if "from jabin_core" in content:
        problems.append(
            "Wrong import: use odoo.addons.jabin_core"
        )

    if "from jabin_api" in content:
        problems.append(
            "Wrong import: use odoo.addons.jabin_api"
        )


    # route checks
    if "@http.route" in content:

        routes = content.count("@http.route")

        if "csrf=False" not in content:
            problems.append(
                f"{routes} route(s) missing csrf=False"
            )

        if "methods=" not in content:
            problems.append(
                "Route missing methods"
            )


    # validation checks
    if "payload.get(" in content:

        if "ValidationHelper" not in content:

            problems.append(
                "Manual payload validation detected, use ValidationHelper"
            )


    # empty class detection
    tree = ast.parse(content)

    for node in ast.walk(tree):

        if isinstance(node, ast.ClassDef):

            if node.name.endswith("Controller"):

                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):

                    continue

                if len(node.body) == 0:
                    problems.append(
                        f"Empty controller class {node.name}"
                    )


    return problems



for root, dirs, files in os.walk(BASE_DIR):

    if "controllers" not in root:
        continue

    for file in files:

        if not file.endswith(".py"):
            continue


        path = os.path.join(root, file)


        syntax_error = check_python_syntax(path)

        if syntax_error:
            print("\n❌", path)
            print("   ", syntax_error)
            continue


        issues = check_controller(path)


        if issues:

            print("\n⚠️", path)

            for issue in issues:
                print("   -", issue)



print("\n========== DONE ==========")