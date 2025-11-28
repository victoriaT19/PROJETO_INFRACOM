import socket
import time
import os

#ARQUIVO_RECEBIDO = "arquivo_recebido.bin"

servidor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
servidor.bind(("0.0.0.0", 5000))

print("Aguardando nome do arquivo...")

nome_arquivo_bytes, endereco_cliente = servidor.recvfrom(1024)
nome_arquivo = nome_arquivo_bytes.decode()
ARQUIVO_RECEBIDO = os.path.join("armazenamento_server",f"recebido_{nome_arquivo}")

print("Servidor UDP aguardando conexões na porta 5000...")

total_bytes = 0

with open(ARQUIVO_RECEBIDO, "wb") as arquivo_recebido:
    while True:
        pacote, endereco_cliente = servidor.recvfrom(1024)
        if pacote == b"FIM":
            print("Recebimento concluído.")
            break
        arquivo_recebido.write(pacote)
        total_bytes += len(pacote)
        print(f"Recebido pacote de {len(pacote)} bytes de {endereco_cliente}.")
    print(f"Arquivo recebido salvo como {ARQUIVO_RECEBIDO} ({total_bytes} bytes).")


pacotes_enviados = 0
total_enviado = 0

with open(ARQUIVO_RECEBIDO, "rb") as arquivo_retorno:
    while True:
        dados = arquivo_retorno.read(1024)
        if not dados:
            break
        servidor.sendto(dados, endereco_cliente)
        pacotes_enviados += 1
        total_enviado += len(dados)
        time.sleep(0.001) ## adicionado para evitar perda de pacotes, pela rapidez do envio
servidor.sendto(b"FIM", endereco_cliente)

print(f"Enviando {pacotes_enviados} pacotes ({total_enviado} bytes) de volta para o cliente...")
print("Envio de confirmação concluído.")

servidor.close()