# Importação Nelogica / Profit

O importador reconhece exportações Tick by Tick com campos como:

- Ativo;
- Data;
- Tempo;
- Número do Negócio;
- Preço;
- Quantidade;
- Agente Comprador;
- Agente Vendedor;
- Agressor;
- After.

## Regras importantes

1. `Tempo` é combinado com `Data`; não é tratado como timestamp completo isolado.
2. `Quantidade` é o tamanho do negócio. Uma coluna de volume financeiro não é usada como substituto.
3. Timestamps iguais são desempantados pela sequência original.
4. IDs repetidos são diagnosticados.
5. Agressor desconhecido permanece `NONE`; não é inferido silenciosamente.
6. Prefira o contrato real (`WINV26`) a séries contínuas (`WINFUT`).

O relatório de importação informa codificação, delimitador, campos reconhecidos, cobertura de agressor, inversões cronológicas e alertas.
