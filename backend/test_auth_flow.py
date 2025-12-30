from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)

def test_auth_flow():
    username = "testuser_auth"
    password = "testpassword123"
    
    # 1. Register
    print("Testing Registration...")
    response = client.post(
        "/register",
        json={"username": username, "password": password, "email": "test@example.com"}
    )
    if response.status_code == 400 and "Username already registered" in response.text:
        print("User already exists, proceeding to login...")
    else:
        assert response.status_code == 200
        print("Registration Successful")

    # 2. Login
    print("Testing Login...")
    response = client.post(
        "/token",
        data={"username": username, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    print("Login Successful, Token received")

    # 3. Access Protected Endpoint (With Token)
    print("Testing Protected Access (With Token)...")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/files", headers=headers)
    assert response.status_code == 200
    print("Protected Access Successful")

    # 4. Access Protected Endpoint (Without Token)
    print("Testing Protected Access (Without Token)...")
    response = client.get("/files")
    assert response.status_code == 401
    print("Access Denied correctly without token")
    
    print("\nALL AUTH TESTS PASSED!")

if __name__ == "__main__":
    # Clean up db if needed, but for now just run
    if os.path.exists("users.db"):
        # os.remove("users.db") # Keep it persistence for now
        pass
    test_auth_flow()
