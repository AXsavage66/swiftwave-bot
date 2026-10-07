from services.cheapdatahub import CheapDataHubService

service = CheapDataHubService()
result = service.get_wallet_balance()

print("Testing Service Integration...")
print(result)