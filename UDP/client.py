import socket
import time
import os

caminho_arquivo = "mapa_westeros.jpg" ## caminho do arquivo que vai ser enviado, deve estar na pasta UDP

#Define o caminho onde o arquivo de retorno será salvo
#O nome do arquivo de retorno será "devolvido_" + nome do arquivo original e sera salvo na pasta "armazenamento_cliente"
ARQUIVO_FINAL = os.path.join("armazenamento_cliente", "devolvido_" + os.path.basename(caminho_arquivo))

#Cria um objeto socket para o cliente
cliente = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
end_servidor =  ("127.0.0.1", 5000) #Define o endereço (IP e porta) do servidor para onde os dados serão enviados."127.0.0.1" é o localhost, que é a própria máquina

#Envia o nome/extensão do arquivo para o servidor
print("Enviando nome/extensão do arquivo para o servidor...")
cliente.sendto(caminho_arquivo.encode(), end_servidor)

#Obtém o tamanho do arquivo a ser enviado
tamanho_arquivo = os.path.getsize(caminho_arquivo)
print(f"Enviando tamanho do arquivo: {tamanho_arquivo} bytes")
cliente.sendto(str(tamanho_arquivo).encode(), end_servidor)

print(f"Enviando arquivo em pacotes de 1024 bytes para o servidor...")

pacotes_enviados = 0
total_enviado = 0

with open(caminho_arquivo, "rb") as arquivo:
    ##Loop para ler o arquivo em pedaços de 1024 bytes e enviar cada pedaço ao servidor
    while True:
        #Lê até 1024 bytes do arquivo
        dados = arquivo.read(1024)
        #Se read() retornar bytes vazios, significa que chegou ao fim do arquivo e então sai do loop
        if not dados:
            break
        #Envia os dados lidos para o endereço do servidor.
        cliente.sendto(dados, end_servidor)
        pacotes_enviados += 1 #contadores
        total_enviado += len(dados)
        time.sleep(0.001) ## adicionado um delayzinho para evitar perda de pacotes, devido a rapidez do envio
print(f"Envio concluído ({pacotes_enviados} pacotes, {total_enviado} bytes). Aguardando confirmação do servidor...")

total_recebido = 0
pacotes_recebidos = 0

print("Aguardando confirmação de tamanho do servidor...")
tamanho_retorno_bytes, _ = cliente.recvfrom(1024)
tamanho_retorno_esperado = int(tamanho_retorno_bytes.decode())
print(f"Servidor confirmou. Recebendo mensagem de {tamanho_retorno_esperado} bytes...")

with open(ARQUIVO_FINAL, "wb") as arquivo_recebido:
    ##Loop para receber os pacotes de volta do servidor
    while total_recebido < tamanho_retorno_esperado:
        ##Recebe pacotes de até 1024 bytes do servidor, p segundo variável endereco_cliente não é necessária aqui
        pacotes_retorno, _ = cliente.recvfrom(1024)
        ##Escreve os dados recebidos no arquivo de retorno
        arquivo_recebido.write(pacotes_retorno)
        total_recebido += len(pacotes_retorno) ##Contadores
        pacotes_recebidos += 1   
print(f"Arquivo recebido salvo como {ARQUIVO_FINAL} ({total_recebido} bytes em {pacotes_recebidos} pacotes)." )

#Fecha o socket do cliente
cliente.close()