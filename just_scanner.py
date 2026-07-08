from bleak import BleakScanner
import asyncio

async def scan_lego_hubs():
    print("Scanning pour les hubs LEGO (5 secondes)...")
    devices = await BleakScanner.discover(timeout=5.0)

    for device in devices:
        print(f"\nNom: {device.name}")
        print(f"Adresse MAC: {device.address}")

        # Affiche les données de la publicité en binaire
        if hasattr(device, 'metadata') and device.metadata:
            print("\nMetadata (en binaire):")
            for key, value in device.metadata.items():
                if isinstance(value, bytes):
                    print(f"  {key}: {value.hex()} (binaire: {' '.join(f'{byte:08b}' for byte in value)})")
                else:
                    print(f"  {key}: {value}")

        if hasattr(device, 'advertisement_data') and device.advertisement_data:
            print("\nAdvertisement Data (en binaire):")
            adv_data = device.advertisement_data
            print(f"  Raw bytes: {adv_data.hex()}")
            print(f"  Binaire: {' '.join(f'{byte:08b}' for byte in adv_data)}")

# Exécute le scan
asyncio.run(scan_lego_hubs())