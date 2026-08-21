from models.user_model import create_user

success, message = create_user(
    username="admin",
    plain_password="Admin@12345",
    fullname="Administrator",
    roleid=1,
    companyid="COM001",
    created_by="system",
)
print(success, message)