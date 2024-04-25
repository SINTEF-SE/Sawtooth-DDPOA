PUB = "(4Zx!?Bz33rJt+u6UYmBOm{eAIBuSEXBeSp+}Sm7"
PRIV = "PnduUi*ZjXn+gO9O$enTQ#%ec)%8{zIQUE3R8sLq"

with open("/etc/sawtooth/validator.toml", "w", encoding="utf-8") as f:
    f.write(f"network_public_key = '{PUB}'\n")
    f.write(f"network_private_key = '{PRIV}'")
