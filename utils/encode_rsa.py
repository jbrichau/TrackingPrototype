import rsa
with open('../Device/rsa_private.pem.txt','rb') as f:
    private_key_txt = f.read()
private_key = rsa.PrivateKey.load_pkcs1(private_key_txt)
print(private_key)