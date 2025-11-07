import socket
import time
import os

#ARQUIVO_RECEBIDO = "arquivo_recebido.bin"

##Cria um objeto socket para o servidor UDP
servidor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
servidor.bind(("0.0.0.0", 5000))##Bind o socket a todas as interfaces de rede na porta 5000

print("Aguardando nome do arquivo...")

##Recebe o nome(extensão) do arquivo do cliente
nome_arquivo_bytes, endereco_cliente = servidor.recvfrom(1024)
nome_arquivo = nome_arquivo_bytes.decode()

###Recebe o tamanho do arquivo esperado do cliente
print("Aguardando tamanho do arquivo...")
tamanho_bytes, endereco_cliente = servidor.recvfrom(1024)
tamanho_esperado = int(tamanho_bytes.decode())
print(f"Nome '{nome_arquivo}', Tamanho: {tamanho_esperado} bytes.")

##Define o caminho onde o arquivo recebido será salvo
ARQUIVO_RECEBIDO = os.path.join("armazenamento_server",f"recebido_{nome_arquivo}")

print("Servidor UDP aguardando conexões na porta 5000...")

total_bytes = 0

with open(ARQUIVO_RECEBIDO, "wb") as arquivo_recebido:
    ##Loop para receber os pacotes do cliente até que o tamanho esperado seja alcançado
    while total_bytes < tamanho_esperado:
        ##Recebe pacotes de até 1024 bytes do cliente
        pacote, endereco_cliente = servidor.recvfrom(1024)
        ##Escreve os dados recebidos no arquivo
        arquivo_recebido.write(pacote) 
        total_bytes += len(pacote) ##atualiza o total de bytes recebidos
        print(f"Recebido pacote de {len(pacote)} bytes de {endereco_cliente}.")
    print(f"Arquivo recebido salvo como {ARQUIVO_RECEBIDO} ({total_bytes} bytes).")


pacotes_enviados = 0 ##Contadores
total_enviado = 0

##Envia a confirmação do tamanho do arquivo de volta para o cliente
print(f"Enviando confirmação de tamanho ({total_bytes} bytes) de volta para o cliente...")
servidor.sendto(str(total_bytes).encode(), endereco_cliente)

##Envia o arquivo de volta para o cliente em pacotes de 1024 bytes
with open(ARQUIVO_RECEBIDO, "rb") as arquivo_retorno:
    ##Loop para ler o arquivo em pedaços de 1024 bytes e enviar cada pedaço ao cliente
    while True:
        ##Lê até 1024 bytes do arquivo
        dados = arquivo_retorno.read(1024)
        ##Se read() retornar bytes vazios, significa que chegou ao fim do arquivo e então sai do loop
        if not dados:
            break
        servidor.sendto(dados, endereco_cliente) ##Envia os dados lidos para o endereço do cliente
        pacotes_enviados += 1 ##atualiza contadores
        total_enviado += len(dados)
        time.sleep(0.001) ## adicionado para evitar perda de pacotes, pela rapidez do envio

print(f"Enviando {pacotes_enviados} pacotes ({total_enviado} bytes) de volta para o cliente...")
print("Envio de confirmação concluído.")

#Fecha o socket do servidor
servidor.close()