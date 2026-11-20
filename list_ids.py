from supplier import client
want = {"freefire-sgmy", "telegram", "pubg-mobile",
        "magic-chess-gogo", "honor-of-kings", "modern-warships"}
for g in client.games():
    if g["slug"] in want:
        print("==", g["slug"], "|", g["name"])
        for p in g["packages"]:
            print(f'{p["package_id"]}|{p["name"]}|{p["price"]}')