import asyncio
import json
import httpx

async def audit():
    async with httpx.AsyncClient() as client:
        # First, find a valid USDC and AQUA issuer
        res = await client.get("http://localhost:8000/v1/graph/assets")
        assets = res.json()["assets"]
        
        usdc = next((a for a in assets if a["code"] == "USDC"), None)
        aqua = next((a for a in assets if a["code"] == "AQUA"), None)
        
        print(f"USDC in graph: {usdc}")
        print(f"AQUA in graph: {aqua}")
        
        if usdc:
            # Let's hit debug endpoint for XLM to USDC
            debug_res = await client.get(f"http://localhost:8000/v1/routes/debug?source_code=XLM&dest_code=USDC&dest_issuer={usdc['issuer']}")
            print(f"XLM -> USDC Debug: {json.dumps(debug_res.json(), indent=2)}")
            
        if aqua:
            debug_res = await client.get(f"http://localhost:8000/v1/routes/debug?source_code=XLM&dest_code=AQUA&dest_issuer={aqua['issuer']}")
            print(f"XLM -> AQUA Debug: {json.dumps(debug_res.json(), indent=2)}")

if __name__ == "__main__":
    asyncio.run(audit())
