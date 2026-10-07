# Guia para dados reais

O MVP precisa de, no mínimo, **trades negócio a negócio** com timestamp, preço e quantidade.

Para análise de agressão são úteis:

- lado agressor;
- comprador;
- vendedor.

Para reconstrução profunda do livro serão necessários eventos L1/L2/MBO/MBP, etapa ainda futura.

## WIN/WDO

Preserve o código do contrato realmente negociado. Não misture vencimentos sob um ticker contínuo sem regra explícita de rollover.

Ao importar, confira o tick size do contrato e a semântica da coluna de quantidade.

Use uma referência OHLC independente quando quiser validar a reconstrução.
