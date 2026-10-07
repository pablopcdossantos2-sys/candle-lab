# Famílias de trajetória — v0.8

Cada candle é convertido em uma trajetória normalizada no tempo e no próprio range.

A análise possui duas camadas:

1. **família interpretável** por regras;
2. **cluster empírico** por k-means determinístico.

Famílias atuais incluem:

- impulso direto de alta/baixa;
- varredura da mínima/máxima com reversão;
- pullback e continuação;
- V-shaped;
- V invertido;
- dupla excursão;
- oscilação/range;
- não classificado.

Uma “varredura” exige excursão real além da abertura antes da reversão. Abrir na mínima e subir monotonicamente não é classificado como varredura.

Clusters dependem do dataset e da versão do modelo e não constituem previsão.
