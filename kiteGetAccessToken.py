#kiteGetAccessToken.py

import logging
import kiteSettings
from kiteconnect import KiteConnect

logging.basicConfig(level=logging.DEBUG)

kite = KiteConnect(kiteSettings.api_key)

#https://kite.zerodha.com/connect/login?v=3&api_key=4630jbpxr6grzx9e
request_token = input("Request Token: ")
data = kite.generate_session(request_token, kiteSettings.api_secret)
kite.set_access_token(data["access_token"])

print("====================")
print("Access Token: ",data["access_token"])