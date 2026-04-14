import os

replacements = {
    "app/api/v1/auth.py": [
        ("if customer_role not in user.roles:\n            user.roles.append(customer_role)", "if user.role_id != customer_role.id:\n            user.role_id = customer_role.id"),
    ],
    "app/api/v1/admin_roles.py": [
        ("user.roles = [role]", "user.role_id = role.id"),
        ("user.roles.append(role)", "user.role_id = role.id")
    ],
    "tests/api/v1/test_audit_integration.py": [
        ("user.roles.append(role)", "user.role_id = role.id")
    ],
    "_run_tests.py": [
        ("user.roles.append(role)", "user.role_id = role.id")
    ]
}

for filepath, reps in replacements.items():
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            content = f.read()
        for old_text, new_text in reps:
            content = content.replace(old_text, new_text)
        with open(filepath, "w") as f:
            f.write(content)

print("Roles assignment fixed.")
