import asyncio, sys, time
from telethon import TelegramClient, functions, types
from telethon.errors import RPCError
from telethon.tl.types import InputPeerSelf
from telethon.tl.functions.payments import GetPaymentFormRequest, SendStarsFormRequest

# ========================= CONFIG =========================

API_ID = 26437284                    # ←←← اینجا API_ID خودت رو بگذار
API_HASH = "9b5a1cb663734dd7b56d0fcd552d030d"                      # ←←← اینجا API_HASH خودت رو بگذار

# نام سشن (می‌تونی عوض کنی، اما بهتره همین بمونه)
SESSION_NAME = "giftbuyer"

LOG_CHAT = "me"
POLL_INTERVAL = 3

PRICE_MIN = 125
PRICE_MAX = 450

ONLY_LIMITED = True

SUPPLY_MIN = 1
SUPPLY_MAX = 100000

RECIPIENTS = ["me"]                # "me" یعنی برای خودت | یا "@username" بگذار

GIFT_TYPES = {
    "limited": False, 
    "birthday": False, 
    "unique": False, 
    "premium_required": False
}

RELEASED_BY = []
HIDE_NAME = True
INCLUDE_UPGRADE = False
MESSAGE_TEXT = ""

# ======================================================

BANNER = r"""
    __  ______    __    _____   ______ _       _______ __ __ ____
   /  |/  /   |  / /   /  _/ | / / __ \ |     / / ___// //_//  _/
  / /|_/ / /| | / /    / //  |/ / / / / | /| / /\__ \/ ,<   / /  
 / /  / / ___ |/ /____/ // /|  / /_/ /| |/ |/ /___/ / /| |_/ /   
/_/  /_/_/  |_/_____/___/_/ |_/\____/ |__/|__//____/_/ |_/___/   
"""

class GiftBuyer:
    def __init__(self, client):
        self.client = client
        self.hash_cache = 0
        self.balance = 0

    async def resolve_peer(self, p):
        try:
            return await self.client.get_input_entity(p)
        except:
            ent = await self.client.get_entity(p)
            return await self.client.get_input_entity(ent)

    def gift_matches(self, g):
        price = getattr(g, "stars", 0) or 0
        limited = bool(getattr(g, "limited", False))
        birthday = bool(getattr(g, "birthday", False))
        sold_out = bool(getattr(g, "sold_out", False))
        avail_total = getattr(g, "availability_total", None)
        unique = hasattr(types, "StarGiftUnique") and isinstance(g, types.StarGiftUnique)
        
        if sold_out: return False
        if price < PRICE_MIN or price > PRICE_MAX: return False
        if ONLY_LIMITED and not limited: return False
        if avail_total is not None and (avail_total < SUPPLY_MIN or avail_total > SUPPLY_MAX): return False
        
        tsel = GIFT_TYPES or {}
        if any([
            tsel.get("limited") is True and not limited,
            tsel.get("limited") is False and limited,
            tsel.get("birthday") is True and not birthday,
            tsel.get("birthday") is False and birthday,
            tsel.get("unique") is True and not unique,
            tsel.get("unique") is False and unique
        ]): return False
        
        prem_req = getattr(g, "require_premium", None)
        if tsel.get("premium_required") is True and not prem_req: return False
        if tsel.get("premium_required") is False and prem_req: return False
        return True

    async def fetch_gifts(self):
        res = await self.client(functions.payments.GetStarGiftsRequest(hash=self.hash_cache))
        if isinstance(res, types.payments.StarGifts):
            self.hash_cache = res.hash
            return list(getattr(res, "gifts", []))
        return []

    async def buy_gift(self, peer, gift, qty):
        successes = 0
        for _ in range(qty):
            try:
                invoice = types.InputInvoiceStarGift(
                    peer=peer,
                    gift_id=getattr(gift, "id"),
                    hide_name=HIDE_NAME or None,
                    include_upgrade=INCLUDE_UPGRADE or None,
                    message=types.TextWithEntities(text=MESSAGE_TEXT or "", entities=[])
                )
                form = await self.client(GetPaymentFormRequest(invoice=invoice))
                await self.client(SendStarsFormRequest(form_id=form.form_id, invoice=invoice))
                successes += 1
                await asyncio.sleep(1)
            except Exception as e:
                await self.log(f"Buy error: {repr(e)}")
                break
        return successes

    async def log(self, msg):
        print(msg, flush=True)
        if LOG_CHAT:
            try:
                await self.client.send_message(LOG_CHAT, msg)
            except:
                pass

    async def run(self):
        gifts = await self.fetch_gifts()
        available = [g for g in gifts if not getattr(g, "sold_out", False)]
        targets = [g for g in available if self.gift_matches(g)]
        
        if not targets:
            return

        for gift in sorted(targets, key=lambda x: getattr(x, "stars", 0), reverse=True):
            price = getattr(gift, "stars", 0) or 0
            if price <= 0 or self.balance < price:
                continue
                
            for r in RECIPIENTS:
                if self.balance < price:
                    break
                qty = self.balance // price
                if qty <= 0:
                    break
                    
                try:
                    peer = await self.resolve_peer(r)
                    bought = await self.buy_gift(peer, gift, qty)
                    if bought > 0:
                        spent = bought * price
                        self.balance -= spent
                        await self.log(f"🎁 Bought {bought} × {price}⭐ for {r}")
                except Exception as e:
                    await self.log(f"Error for {r}: {repr(e)}")

    async def loop(self):
        print(BANNER)
        await self.log("🚀 Gift Buyer Bot Started")
        
        stars_status = await self.client(functions.payments.GetStarsStatusRequest(peer=types.InputPeerSelf()))
        self.balance = getattr(getattr(stars_status, "balance", None), "amount", 0)
        
        me = await self.client.get_me()
        await self.log(f"👤 {me.first_name} | Balance: {self.balance}⭐")

        while True:
            try:
                await self.run()
            except Exception as e:
                await self.log(f"Cycle error: {repr(e)}")
            
            await asyncio.sleep(POLL_INTERVAL)

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()          # اگر سشن نباشه، خودش شماره و کد می‌پرسه
    buyer = GiftBuyer(client)
    await buyer.loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
        sys.exit(0)
