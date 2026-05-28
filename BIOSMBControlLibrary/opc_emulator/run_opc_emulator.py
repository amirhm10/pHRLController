import asyncio
from biosmb_opc_emulator import BioSMBOPCEmulator

if __name__ == "__main__":
    ip_address= "0.0.0.0"
    tcpip_port = 4842

    server = BioSMBOPCEmulator(ip_address, tcpip_port)
    asyncio.run(server.run_server(), debug=True)