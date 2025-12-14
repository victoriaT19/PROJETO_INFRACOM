# Projeto de Redes: Transferência de Arquivos sobre UDP

Este é um projeto acadêmico para a disciplina de Infraestrutura de Comunicações (Infracom) que implementa um protocolo de transferência de arquivos utilizando UDP. A comunicação é feita com sockets Python puros, sem bibliotecas de alto nível.

## Status do Projeto

:warning: **Etapa 1 do projeto.**

O foco desta etapa é implementar a transferência básica de um arquivo do Cliente para o Servidor, e a devolução (retorno) do Servidor de volta ao Cliente.

Nesta fase, a transferência **não é confiável**. Ela é suscetível a:

  - Perda de pacotes
  - Pacotes fora de ordem
  - Duplicação de pacotes

A solução para estes problemas (implementação de confiabilidade) será o foco da **Etapa 2**.

## Funcionalidades (Etapa 1)

  - **Cliente (`client.py`) e Servidor (`server.py`)** modularizados.
  - Comunicação via **UDP** (`SOCK_DGRAM`).
  - **Protocolo de Aplicação Customizado:** Um protocolo simples foi criado "por cima" do UDP para permitir a transferência, informando metadados essenciais (nome e tamanho) antes dos dados.
  - **Transferência de Arquivo:** O Cliente envia um arquivo para o Servidor.
  - **Armazenamento:** O Servidor salva o arquivo recebido na pasta `armazenamento_server/`.
  - **Confirmação (Retorno):** O Servidor devolve o mesmo arquivo ao Cliente como forma de confirmação.
  - **Verificação:** O Cliente salva o arquivo devolvido em `armazenamento_cliente/`.

## Como Funciona: O Protocolo de Aplicação

Como o UDP não oferece garantias, foi necessário criar um conjunto de regras (um protocolo) para que o Cliente e o Servidor se entendam. A sequência de comunicação é a seguinte:

1.  **[Cliente -\> Servidor]:** Envia o `nome_do_arquivo` (ex: `"teste.pdf"`).
2.  **[Cliente -\> Servidor]:** Envia o `tamanho_do_arquivo` (ex: `"1048576"` bytes).
3.  **[Cliente -\> Servidor]:** Envia os `dados_do_arquivo` em pacotes de 1024 bytes, até que o tamanho total seja enviado.
4.  O Servidor recebe os pacotes e salva o arquivo em `armazenamento_server/recebido_[nome_do_arquivo]`.
5.  **[Servidor -\> Cliente]:** Envia o `tamanho_total_recebido` de volta ao Cliente (atua como uma confirmação de tamanho para o eco).
6.  **[Servidor -\> Cliente]:** Envia os `dados_do_arquivo` (lendo o arquivo que acabou de salvar) de volta ao Cliente, também em pacotes de 1024 bytes.
7.  O Cliente recebe os dados do retorno e salva o arquivo em `armazenamento_cliente/devolvido_[nome_do_arquivo]`.

## Estrutura de Pastas

Para que o projeto funcione, a seguinte estrutura de pastas deve ser criada:

```
UDP/
├── armazenamento_cliente/    <-- (O cliente salva o retorno aqui)
├── armazenamento_server/     <-- (O servidor salva o upload aqui)
├── client.py                 <-- (Nosso script de cliente)
├── server.py                 <-- (Nosso script de servidor)
└── exemplo.extensão          <-- (Coloque aqui o arquivo que deseja enviar)
```

## Como Usar

### 1\. Pré-requisitos

  - Python 3.x

### 2\. Configuração

1.  Clone este repositório (ou baixe os arquivos).
2.  Coloque um arquivo que você deseja testar na pasta UDP (ex: `teste.txt` ou `imagem.png`).
3.  Abra o arquivo `client.py` e altere a variável `caminho_arquivo` para o nome do seu arquivo:
    ```python
    # Altere esta linha
    caminho_arquivo = "nome_do_arquivo" 
    ```

### 3\. Execução

Você precisará de **dois terminais** abertos na pasta do projeto.

**No Terminal 1 (Servidor):**

Execute o servidor. Ele ficará aguardando conexões.

```bash
python server.py
```

*Saída esperada:*

```
Aguardando nome do arquivo...
```

**No Terminal 2 (Cliente):**

Execute o cliente.

```bash
python client.py
```

*Saída esperada:*

```
Enviando nome/extensão do arquivo para o servidor...
Enviando tamanho do arquivo: [tamanho] bytes
Enviando arquivo em pacotes de 1024 bytes para o servidor...
Envio concluído (...). Aguardando confirmação do servidor...
Aguardando confirmação de tamanho do servidor...
Servidor confirmou. Recebendo mensagem de [tamanho] bytes...
Arquivo recebido salvo como armazenamento_cliente/devolvido_nome_do_arquivo (...)
```

### 4\. Verificação

Após a execução, verifique as pastas `armazenamento_server` e `armazenamento_cliente`. Você deverá ver os arquivos `recebido_nome_do_arquivo` e `devolvido_nome_do_arquivo`, respectivamente.

## Próximas Etapas (Etapa 2)

A implementação atual é ingênua. O `time.sleep(0.001)` é um "hack" para evitar que o remetente sobrecarregue o buffer do receptor.

A **Etapa 2** deste projeto focará na implementação de um **Protocolo de Transferência Confiável sobre o UDP**, o que envolverá:

  - **Números de Sequência:** Para ordenar os pacotes.
  - **Confirmações (ACKs):** Para confirmar o recebimento de cada pacote.
  - **Temporizadores (Timeouts):** Para detectar pacotes perdidos.
  - **Retransmissão:** Para reenviar pacotes perdidos ou corrompidos.

# HuntCin - Terceira Etapa (Entrega 3)

## Status do Projeto
-----------------
⚠️ Esta é a Etapa 3 do projeto. Nesta entrega o foco é a aplicação final: um jogo multiplayer "Caça ao Tesouro"
rodando em linha de comando com comunicação UDP e transmissão confiável implementada em camada de aplicação (RDT 3.0).

## Resumo rápido
-------------
- Projeto: HuntCin — Caça ao Tesouro (multiplayer, client-server)
- Linguagem: Python 3.x
- Comunicação: UDP com camada de confiabilidade (RDT 3.0 - alternating-bit / pare-e-espere)
- Arquivos principais: server.py, client.py

## O que foi implementado
-----------------------
- Servidor UDP que aceita múltiplos clientes (cada cliente é um processo com porta única).
- Login / logout com nomes únicos (não aceitamos nomes duplicados).
- Grid 3x3. Posição inicial de todos: (1,1).
- Tesouro sorteado aleatoriamente (qualquer posição exceto (1,1)).
- Rodadas temporizadas (ROUND_TIME = 30s por padrão). Se o cliente não enviar comando dentro do tempo,
  será considerado sem comando nesta rodada.
- Comandos:
    - login <nome_do_usuario>
    - logout
    - move <up|down|left|right>
    - hint  (cada jogador tem direito a 1 hint por partida)
    - suggest (cada jogador tem direito a 1 suggest por partida)
- Mensagens de controle e broadcast são enviadas de forma confiável (RDT stop-and-wait) do servidor para cada cliente.
- Cliente envia comandos ao servidor usando RDT stop-and-wait.
- Placar acumulado por jogador (persistência em memória durante a execução).

## Estrutura de pastas 
-------------------------------------
```
HuntCin/
├── client.py
└── server.py
```

## Como usar (execução local / testes)
-----------------------------------
  ### 1. Pré-requisitos:
    - Python 3.x (3.7+ recomendado)

  ### 2. Configuração:
    - Clone / copie os arquivos para a pasta UDP/
    - Por padrão, a simulação de perda está DESATIVADA (PROB_PERDA = 0.0) em server.py e client.py.
      Para testar robustez com perdas, altere PROB_PERDA para um valor entre 0 e 1 (ex.: 0.2).

  ### 3. Execução:
    - Abra um terminal para o servidor:
        python server.py
      O servidor iniciará e começará o loop de rodadas automaticamente.

    - Abra ao menos dois terminais para clientes diferentes (cada cliente terá porta local diferente):
        python client.py
      No prompt do cliente, use comandos:
        login <nome>
        move <up|down|left|right>
        hint
        suggest
        logout
        exit

    - Exemplo de sequência:
        > login João
        [Servidor] você está online!
        (quando a rodada iniciar)
        > move up
        > move right
        ...

  ### 4. Observações de teste:
    - Rode dois (ou mais) clientes em terminais distintos para testar simultaniedade.
    - Verifique no terminal do servidor o log das rodadas, entradas e placar.
    - Caso queira testar perda de pacotes, defina PROB_PERDA = 0.2 (ou outro valor) em ambos os arquivos.

## Notas / limitações
------------------
- A camada RDT é do tipo stop-and-wait (alternating bit). Isso cumpre os requisitos da disciplina,
  porém não é eficiente para redes de alta latência/alto throughput.
- O servidor mantém estado por endereço (ip,port). Em cenários NAT/endereços dinâmicos pode ser necessário
  adaptar identificação (por ex. associar identificador de sessão).
- Persistência de placar é em memória (não há armazenamento em arquivo).
- Regras de "eliminado da rodada" estão implementadas como: quem não enviar comando dentro do tempo
  simplesmente não movimenta e recebe aviso de eliminado (pode-se ajustar comportamento conforme necessidade).

## Autores

- Victória Tauanny de Paula da Silva
- Gilberto Andrade Patricio
- Karoline Fonseca Viana
- Luany Bezerra dos Reis
