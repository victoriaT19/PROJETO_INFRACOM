import socket
import time
import os

caminho_arquivo = "Lorem.pdf"
ARQUIVO_FINAL = os.path.join("armazenamento_cliente", "devolvido_" + os.path.basename(caminho_arquivo))

cliente = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
end_servidor =  ("127.0.0.1", 5000)

print("Enviando nome/extensão do arquivo para o servidor...")

cliente.sendto(caminho_arquivo.encode(), end_servidor)

print(f"Enviando arquivo em pacotes de 1024 bytes para o servidor...")

pacotes_enviados = 0
total_enviado = 0

with open(caminho_arquivo, "rb") as arquivo:
    while True:
        dados = arquivo.read(1024)
        if not dados:
            break
        cliente.sendto(dados, end_servidor)
        pacotes_enviados += 1
        total_enviado += len(dados)
        time.sleep(0.001) ## adicionado para evitar perda de pacotes, devido a rapidez do envio
cliente.sendto(b"FIM", end_servidor)
print(f"Envio concluído ({pacotes_enviados} pacotes, {total_enviado} bytes). Aguardando confirmação do servidor...")

total_recebido = 0
pacotes_recebidos = 0

with open(ARQUIVO_FINAL, "wb") as arquivo_recebido:
    while True:
        pacotes_retorno, _ = cliente.recvfrom(1024)
        if pacotes_retorno == b"FIM":
            print("Confirmação de recebimento concluída.")
            break
        arquivo_recebido.write(pacotes_retorno)
        total_recebido += len(pacotes_retorno)
        pacotes_recebidos += 1   
print(f"Arquivo recebido salvo como {ARQUIVO_FINAL} ({total_recebido} bytes em {pacotes_recebidos} pacotes)." )

cliente.close()