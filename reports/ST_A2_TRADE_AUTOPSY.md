# ST-A2 Trade Autopsy

Scope: `run_id=20260621T100458-183aaa` | `rr=5.0` | `trades=169` | `losses=115` | `wins=54`

Methodology:
- `Sweep type` is derived from trade direction: long = bullish sweep, short = bearish sweep.
- `BOS quality` is a proxy from displacement body/ATR and close location, because the raw trade ledger does not store a separate BOS score.
- `FVG size` is computed from the repo's 3-bar FVG rule around the displacement bar.

## Executive Summary

- Loss rate: 115/169 (68.0%)
- Median spread: 1.40 pips
- Median BOS strength proxy (body/ATR): 1.523
- Median FVG size: 5.90 pips

## Loss Table

| Trade ID | Session | Direction | Sweep type | BOS quality | FVG size (pips) | ATR (pips) | Spread (pips) | Result |
|---|---|---|---|---|---:|---:|---:|---:|
| a73f74e6-807c-46a2-bff1-42795e2bbdca | new_york | long | bullish | medium | n/a | 8.04 | 1.40 | -1.087R |
| 98012930-0df1-4748-a2f3-18cf7692e8c6 | london | long | bullish | strong | n/a | 5.15 | 1.40 | -1.109R |
| a8a21c93-7b8c-41eb-82e5-9cd67921525a | london | short | bearish | medium | 1.0 | 4.43 | 1.40 | -1.102R |
| cd9931ad-4b46-485e-b4c6-86df5f245946 | london | short | bearish | strong | 7.1 | 6.41 | 1.40 | -1.053R |
| 3432db99-55a1-4434-8e27-ff05ce52518f | london | long | bullish | strong | 8.5 | 5.93 | 1.40 | -1.049R |
| a6da674e-5cb0-4273-ae03-96bb0448be2b | london | long | bullish | medium | 3.2 | 4.01 | 1.40 | -1.065R |
| be07e8c9-4d20-460b-accb-63b00bce6a38 | london | short | bearish | strong | 10.2 | 5.46 | 1.40 | -1.075R |
| 7ea69d2f-0752-42a1-8098-b2949ac8ad06 | london | long | bullish | strong | 2.4 | 3.92 | 1.40 | -1.109R |
| 0037038f-fb6e-4da6-b6bb-ec39bb015cc4 | new_york | long | bullish | medium | n/a | 5.8 | 1.40 | -1.149R |
| 42296d47-df3e-4636-93e1-6b06d3490b9e | london | short | bearish | strong | 3.9 | 7.1 | 1.40 | -0.134R |
| e9cd2ced-d53d-49f6-9907-e7d6a29788f7 | london | long | bullish | strong | n/a | 4.02 | 1.40 | -1.151R |
| bcd7fc3c-915b-469c-81a0-8363c19a0219 | london | long | bullish | medium | n/a | 5.64 | 1.40 | -1.093R |
| 5843aa2c-8c73-4700-9577-fee574f3bc77 | london | long | bullish | medium | 0.6 | 5.83 | 1.40 | -1.088R |
| a00f82f5-d893-403f-a1c8-ead8810eef47 | london | short | bearish | strong | 1.8 | 4.73 | 1.40 | -1.179R |
| 5a136b2d-61a6-4ab5-9c55-854e8e9e5afc | new_york | short | bearish | strong | n/a | 10.8 | 1.40 | -1.095R |
| 51450a9c-c5cb-408f-948a-a669fefb87a0 | new_york | long | bullish | strong | 0.6 | 12.78 | 1.40 | -1.038R |
| 4092b5dd-1881-4273-a9c3-9a830a6490b7 | london | short | bearish | strong | n/a | 7.58 | 1.40 | -1.173R |
| 57d42b6d-64d5-40c4-aba7-bd03dcb57ed8 | london | long | bullish | strong | 1.1 | 6.0 | 1.40 | -1.067R |
| f582fa04-f330-4ce0-bd94-521a88c19b5c | london | long | bullish | strong | n/a | 7.38 | 1.40 | -1.067R |
| 6d004c1a-f0de-4e0c-b4f8-dec129709b0e | london | short | bearish | strong | 5.1 | 6.18 | 1.40 | -1.072R |
| 3e2b24ee-d667-4cd2-91fb-b958aa8153bb | new_york | long | bullish | medium | n/a | 8.46 | 1.40 | -1.119R |
| 911b2e10-a244-4963-9c28-a0f6410aeb01 | new_york | long | bullish | medium | 4.5 | 14.48 | 1.40 | -1.019R |
| e9ae7ff5-700d-4eb4-a2e3-e8c35720733e | london | long | bullish | strong | 7.7 | 9.94 | 1.40 | -1.076R |
| b3f24213-bf63-4a54-b3b6-7471b51a1781 | london | short | bearish | medium | n/a | 7.95 | 1.40 | -1.073R |
| aabb604f-8423-4a33-98c1-ded8c3663ebc | london | short | bearish | medium | n/a | 10.59 | 1.40 | -1.050R |
| 49b26b8e-a38c-4848-80ee-4f3789d8a7e7 | london | short | bearish | medium | 4.1 | 9.49 | 1.40 | -1.057R |
| e589b136-5ff3-4046-adc8-467d89f5ea8d | new_york | long | bullish | strong | 39.1 | 17.22 | 1.40 | -1.019R |
| d1ee3331-d245-42d2-9e27-fe4d2c0f7607 | new_york | short | bearish | medium | 0.9 | 14.16 | 1.40 | -1.034R |
| 76af6319-c6cc-4c7e-a8b7-8f1efb0d7a3b | new_york | long | bullish | strong | 0.3 | 9.89 | 1.40 | -1.092R |
| 580dd4d3-2d91-4560-b10a-e5cd92dc20d4 | london | long | bullish | medium | n/a | 6.91 | 1.40 | -1.075R |
| 7b617377-ffec-4345-a4bf-3afb319ee3db | london | long | bullish | medium | 2.3 | 5.03 | 1.40 | -1.077R |
| ebdfe9f8-1931-4193-a60c-c7ed85c320b4 | london | short | bearish | medium | n/a | 4.53 | 1.40 | -1.200R |
| 78520f07-405a-483f-9fed-7e4f38cb8693 | london | long | bullish | strong | 6.1 | 5.53 | 1.40 | -1.102R |
| 87b80315-44f1-4d5e-980b-5811ff1d6078 | london | long | bullish | strong | 2.9 | 3.99 | 1.40 | -1.116R |
| 2b1aadc7-d8ed-4ca9-bb7d-57d0c170c425 | london | short | bearish | medium | n/a | 5.12 | 1.40 | -1.184R |
| ee6fc59a-dc20-46a0-a187-fb48786ba296 | london | long | bullish | medium | 3.2 | 8.29 | 1.40 | -1.050R |
| a82cc0e3-b571-45c3-84ea-1dd82267e919 | london | short | bearish | strong | 33.0 | 10.21 | 1.40 | -0.021R |
| 44074595-23cf-4a31-af69-2092072eace9 | new_york | long | bullish | strong | 7.8 | 6.12 | 1.40 | -1.069R |
| c6645765-6c80-4749-a3db-cb9b3cd22ab6 | new_york | short | bearish | medium | n/a | 5.86 | 1.40 | -1.106R |
| a1c95ffc-89e2-43e0-b47e-39b31317f5fe | new_york | short | bearish | medium | n/a | 5.58 | 1.40 | -1.110R |
| 64ca0b1a-2797-414b-9089-6792cd70246b | london | short | bearish | medium | n/a | 5.11 | 1.40 | -1.079R |
| ff9f4fb0-cfe3-4c94-b0a3-8fe688e1de15 | london | short | bearish | medium | n/a | 5.16 | 1.40 | -1.140R |
| 23319f6b-5daf-45ff-83a5-8cf961c2e0db | london | short | bearish | medium | n/a | 4.02 | 1.40 | -1.156R |
| 8676deab-274e-42cd-bb6a-a166ab942fab | london | long | bullish | medium | n/a | 4.6 | 1.40 | -1.066R |
| 75f4ff3e-40e1-4785-88a4-8c2b86d23e79 | london | long | bullish | strong | 4.0 | 7.59 | 1.40 | -1.055R |
| da7e6198-7e79-4253-9b7c-bb1493c41111 | london | long | bullish | medium | n/a | 4.14 | 1.40 | -1.112R |
| ee4dad7f-d2ac-4795-a90e-d4d04651acaf | london | long | bullish | strong | 4.4 | 3.77 | 1.40 | -1.089R |
| bdd7a88d-1162-4b55-a4c6-fd1b51ddd791 | london | long | bullish | strong | 8.0 | 7.1 | 1.40 | -1.041R |
| b7746b67-45b3-402a-8c45-e5b5c3b61d63 | london | short | bearish | strong | 5.3 | 5.99 | 1.40 | -0.374R |
| b80c3c2a-03b8-4de8-be7a-4f07c9693ea5 | london | long | bullish | medium | n/a | 4.87 | 1.40 | -1.097R |
| c17e54db-ee41-404a-ba88-d8a5d0fd6829 | london | short | bearish | strong | n/a | 3.93 | 1.40 | -1.126R |
| 4579efb8-35cc-4066-90d5-448bc0c53534 | london | long | bullish | medium | n/a | 3.19 | 1.40 | -1.200R |
| 12e3c685-d9a8-450e-a3e0-1f268295bd81 | london | long | bullish | medium | 0.5 | 5.76 | 1.40 | -1.092R |
| 2f417ebf-5ada-4293-a991-b166b9a641ff | london | long | bullish | strong | 1.8 | 4.44 | 1.40 | -1.122R |
| d8092528-49bb-4972-bafa-ecd3cefe497c | london | short | bearish | strong | 3.4 | 3.84 | 1.40 | -1.139R |
| c507e4a4-0c0c-480c-aa9b-f863907fcd04 | london | short | bearish | strong | 22.1 | 10.67 | 1.40 | -1.031R |
| c356b849-eed7-457e-8c5e-65beba8ae29c | new_york | long | bullish | strong | n/a | 6.78 | 1.40 | -1.107R |
| 6bff0f1f-6150-4828-95e0-0af7986f2f55 | london | short | bearish | medium | 22.0 | 10.44 | 1.40 | -1.030R |
| a8a87be4-235a-4dfe-82aa-0138c2cd760b | london | long | bullish | medium | n/a | 6.1 | 1.40 | -1.075R |
| e4d01535-3649-492c-8d6d-81f0f771add1 | london | long | bullish | strong | 7.8 | 3.98 | 1.40 | -1.075R |
| 790c06d1-9fe8-4695-ab33-14ec3d760102 | new_york | short | bearish | medium | n/a | 10.8 | 1.40 | -1.097R |
| 72183f2b-e985-459f-a0a2-c9d18083fe81 | london | short | bearish | strong | 18.4 | 19.22 | 1.40 | -1.021R |
| a5e084cb-6810-4977-851d-a13a9442d1ad | new_york | long | bullish | medium | 7.0 | 9.54 | 1.40 | -1.081R |
| 2e746c24-f9d8-4189-8d9d-e58d38324c68 | london | long | bullish | strong | 14.9 | 8.69 | 1.40 | -1.041R |
| c379f066-4621-4989-8b74-835e5a54e760 | london | long | bullish | medium | 3.7 | 3.88 | 1.40 | -1.118R |
| 5daeb4cf-3171-4c83-b705-1d53026dcad4 | london | short | bearish | medium | n/a | 3.89 | 1.40 | -1.118R |
| 7ff136e1-25ea-40be-b282-015f847f0d61 | new_york | long | bullish | strong | 8.5 | 6.86 | 1.40 | -1.053R |
| 13d4100f-3128-4951-97bc-c8b38f352372 | london | short | bearish | medium | 4.6 | 6.73 | 1.40 | -0.789R |
| 1ba4596f-5a3d-400f-be9e-f99160563b01 | london | long | bullish | strong | 5.1 | 5.34 | 1.40 | -1.083R |
| 0f280cdc-d17d-4891-97eb-9dc10aed17d9 | london | long | bullish | medium | n/a | 5.29 | 1.40 | -1.222R |
| e5eeaf71-231c-40a6-9ff1-454e461b97df | london | short | bearish | strong | 5.5 | 6.33 | 1.40 | -1.084R |
| 3e5ef72e-b507-45df-9d1d-e3c32f720434 | london | long | bullish | medium | 2.2 | 10.3 | 1.40 | -1.060R |
| b85245bd-ae22-4dec-b3de-fb70c9ffbc9f | london | short | bearish | medium | n/a | 5.71 | 1.40 | -1.197R |
| ce1f7dd4-9bfd-483e-a46f-65155251bb76 | new_york | short | bearish | medium | 4.4 | 5.93 | 1.40 | -1.090R |
| 8fd5a57e-0467-4540-bd14-7eebd810e7a7 | london | long | bullish | medium | n/a | 12.55 | 1.80 | -1.075R |
| cf04991e-82a4-4255-a174-3484147a4f6d | london | long | bullish | strong | 0.2 | 6.36 | 1.80 | -1.129R |
| 9e03eb1a-d340-477d-8ffd-81cd5e0d3e15 | london | long | bullish | medium | n/a | 10.62 | 1.80 | -1.129R |
| 35a20bba-3fa2-4f85-9153-7680759f2482 | new_york | short | bearish | medium | 7.6 | 7.75 | 1.80 | -1.089R |
| 84697f70-5dd5-4e9e-8618-5f686b0abfac | london | long | bullish | strong | 0.5 | 6.27 | 1.80 | -1.074R |
| e2daa7a9-7a8c-4fa3-86b0-008026cb6a7c | new_york | long | bullish | strong | 9.1 | 9.54 | 1.80 | -1.066R |
| b48305d8-107f-4392-b4f7-6d82ac511f2f | new_york | short | bearish | strong | 12.4 | 9.72 | 1.80 | -1.069R |
| c945fcd4-2c19-457a-a30f-4217746f0ea2 | new_york | short | bearish | medium | n/a | 9.66 | 1.80 | -1.069R |
| 25d21658-e707-4890-a023-cbb9efb96082 | london | short | bearish | strong | 8.2 | 6.7 | 1.80 | -1.111R |
| f0ed3ec7-ec65-4ba5-92bf-a46b0324c2a7 | london | long | bullish | strong | 7.9 | 5.87 | 1.80 | -1.081R |
| e0b2bf44-84c1-4b01-bac6-ec884561c4a6 | london | long | bullish | strong | n/a | 5.1 | 1.80 | -1.119R |
| 715e0c6a-d22b-4947-8d1e-9cd89f9eff25 | new_york | long | bullish | medium | 4.0 | 10.91 | 1.80 | -1.040R |
| afc7213e-38b9-4b72-a5ee-c56f4818b32e | london | long | bullish | strong | 8.3 | 6.75 | 1.80 | -1.079R |
| 5e5e8df1-97aa-4600-b623-8dbd7cb14f47 | london | long | bullish | medium | 1.7 | 8.75 | 1.80 | -1.063R |
| afdca420-51f5-4ccf-aa80-d346fb838c8a | london | long | bullish | strong | 2.8 | 7.51 | 1.80 | -1.100R |
| ba3f3b45-fd7b-452f-8abb-d93aa83ada7d | london | short | bearish | strong | 1.7 | 6.87 | 1.80 | -1.100R |
| 16af8ed0-9406-4f3a-8438-dab299bf277f | london | short | bearish | medium | n/a | 5.18 | 1.80 | -1.116R |
| b712bd41-80d8-4bec-86f0-a08f22f6c301 | new_york | short | bearish | strong | 45.1 | 12.64 | 1.80 | -1.025R |
| 41ec6327-47da-482c-a2f9-0e835001a114 | london | long | bullish | strong | n/a | 7.58 | 1.80 | -1.086R |
| e0d47b7f-f867-46e4-85a6-c51ee97c23e9 | new_york | short | bearish | strong | n/a | 9.65 | 1.80 | -1.063R |
| 9dd94197-2efa-45e1-8106-f4d1e529efc1 | london | long | bullish | medium | n/a | 7.51 | 1.80 | -1.089R |
| a599bc4c-c87c-4121-bec5-fc0fa7b7bfd7 | new_york | long | bullish | medium | n/a | 9.48 | 1.80 | -1.076R |
| f9f7c2e4-33d9-4822-a7a5-eb907fe3a3a7 | london | long | bullish | medium | 5.9 | 5.3 | 1.80 | -1.079R |
| 1311d9c3-689a-45d6-9d8a-f33f9a2d858d | london | long | bullish | medium | n/a | 5.52 | 1.80 | -1.133R |
| 21c8d3dd-8e73-4ab5-954e-df73bc1bd32c | london | long | bullish | strong | 9.1 | 5.11 | 1.80 | -1.101R |
| 4a7bf27b-e697-47a5-8651-39f432f3d132 | new_york | long | bullish | medium | n/a | 9.46 | 1.80 | -1.113R |
| 3bef85a1-245e-4ad8-9074-b67d01d7841e | london | long | bullish | medium | n/a | 8.05 | 1.80 | -1.098R |
| 1dc13229-0045-4343-88a4-5b1565aa6082 | london | long | bullish | strong | 8.1 | 9.24 | 1.80 | -1.064R |
| 5551f72b-44ef-47f4-898d-3d7f1eaf5626 | london | short | bearish | strong | n/a | 7.14 | 1.80 | -1.086R |
| 7f12be36-d9d9-4921-b35b-96e0d288de91 | london | short | bearish | strong | 18.3 | 7.66 | 1.80 | -1.045R |
| fb059dee-d998-4a18-8b32-effd30bbd332 | london | long | bullish | strong | 37.1 | 17.47 | 1.80 | -1.027R |
| 5b2d4fb5-ade0-492b-a6b7-a5efc462f6df | london | short | bearish | medium | n/a | 6.96 | 1.80 | -1.269R |
| c595e8a6-2c96-4dd3-b1b8-49314219d143 | london | short | bearish | medium | 8.7 | 9.07 | 1.80 | -1.068R |
| 82d13949-5a5a-4983-adb7-996cd3671522 | new_york | long | bullish | medium | 9.8 | 9.09 | 1.80 | -0.126R |
| c94e1bcf-c20d-429d-a646-9b9eb1eb3e5e | london | long | bullish | strong | 7.3 | 5.81 | 1.80 | -1.095R |
| 766ed418-af5b-4570-992a-c06f0c39b1fb | london | short | bearish | strong | 10.5 | 7.33 | 1.80 | -1.071R |
| e632a520-68d4-43a4-9b25-4ecc2f86b70c | london | long | bullish | medium | n/a | 5.63 | 1.80 | -1.097R |
| 4101f323-42bc-4165-8afa-4e7631f89d16 | new_york | long | bullish | medium | 9.5 | 11.1 | 1.80 | -1.067R |
| fcebff81-e69d-4ade-98b5-72f0b4729935 | new_york | long | bullish | strong | 7.6 | 10.25 | 1.80 | -1.069R |
| f3823d53-1d43-4d56-9c13-13f27b47e879 | london | short | bearish | strong | 14.7 | 9.19 | 1.80 | -1.060R |
| 92e9e211-7482-468c-863b-7818eaa0fea4 | new_york | short | bearish | strong | n/a | 9.06 | 1.80 | -1.096R |

## Breakdown By Dimension

### Primary Cause Heuristic

| Bucket | Count | Share |
|---|---:|---:|
| random | 52 | 45.2% |
| large_spread | 32 | 27.8% |
| NY_session | 18 | 15.7% |
| small_FVG | 13 | 11.3% |

### Session

| Bucket | Count | Share |
|---|---:|---:|
| london | 85 | 73.9% |
| new_york | 30 | 26.1% |

### Sweep Type

| Bucket | Count | Share |
|---|---:|---:|
| bullish | 68 | 59.1% |
| bearish | 47 | 40.9% |

### BOS Quality

| Bucket | Count | Share |
|---|---:|---:|
| strong | 59 | 51.3% |
| medium | 56 | 48.7% |

### Spread Bucket

| Bucket | Count | Share |
|---|---:|---:|
| medium | 62 | 53.9% |
| large | 32 | 27.8% |
| small | 21 | 18.3% |

### FVG Size Bucket

| Bucket | Count | Share |
|---|---:|---:|
| unknown | 46 | 40.0% |
| medium | 34 | 29.6% |
| large | 18 | 15.7% |
| small | 17 | 14.8% |

### BOS Strength Proxy Bucket

| Bucket | Count | Share |
|---|---:|---:|
| medium | 57 | 49.6% |
| large | 29 | 25.2% |
| small | 29 | 25.2% |

## Loss Rate By Dimension

### Session Loss Rate

| Bucket | Trades | Losses | Loss rate | Avg net R |
|---|---:|---:|---:|---:|
| london | 118 | 85 | 72.0% | -0.039R |
| new_york | 51 | 30 | 58.8% | +0.449R |

### Sweep Type Loss Rate

| Bucket | Trades | Losses | Loss rate | Avg net R |
|---|---:|---:|---:|---:|
| bullish | 99 | 68 | 68.7% | +0.100R |
| bearish | 70 | 47 | 67.1% | +0.119R |

### BOS Quality Loss Rate

| Bucket | Trades | Losses | Loss rate | Avg net R |
|---|---:|---:|---:|---:|
| strong | 88 | 59 | 67.0% | +0.138R |
| medium | 81 | 56 | 69.1% | +0.076R |

### Spread Bucket Loss Rate

| Bucket | Trades | Losses | Loss rate | Avg net R |
|---|---:|---:|---:|---:|
| medium | 90 | 62 | 68.9% | +0.157R |
| large | 51 | 32 | 62.7% | +0.209R |
| small | 28 | 21 | 75.0% | -0.233R |

### FVG Quality Loss Rate

| Bucket | Trades | Losses | Loss rate | Avg net R |
|---|---:|---:|---:|---:|
| unknown | 59 | 46 | 78.0% | -0.334R |
| medium | 54 | 34 | 63.0% | +0.240R |
| large | 28 | 18 | 64.3% | +0.094R |
| small | 28 | 17 | 60.7% | +0.800R |

## Takeaway

The autopsy is intentionally exclusive at the `Primary Cause Heuristic` level, while the other tables are dimension-wise breakdowns.
Use the primary cause to decide what to improve first; use the dimension tables to verify whether the issue clusters around session timing, spread, or weak confirmation.

Largest session loss cluster: **london** (85/115 losses, 73.9%).

Most likely improvement target: **random** (52/115 losses, 45.2%).

## Notes

- Spread bucket thresholds are derived from the full 169-trade sample: q25=1.40, q50=1.40, q75=1.80.
- BOS proxy thresholds (body/ATR): q25=1.351, q50=1.523, q75=1.933.
- FVG thresholds: q25=2.90 pips, q50=5.90 pips, q75=8.70 pips.
