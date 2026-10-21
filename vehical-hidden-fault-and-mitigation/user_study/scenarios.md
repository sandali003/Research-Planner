# XAI user study: scenario cards

Generated from the live hidden fault system (`python user_study/make_materials.py`). Each participant sees every scenario once, in one version; the version per scenario rotates between participants (see protocol.md). Remove the answer key lines before printing.

---

## S1: Idling at a car sale

| Reading | Value |
|---|---|
| Engine speed | 800 rpm |
| Engine load | 5 % |
| Coolant temperature | 82 °C |
| Battery voltage | 15.30 V |

### Version A (scanner)

**Trouble codes:** P0563 System Voltage High

### Version B (prediction)

**Result:** Fault detected

- **Charging System Warning**, confidence 100%, severity High

### Version C (explainable system)

**Charging System Warning**, confidence 100%, severity High (act: Immediately (within 1-2 days))
- **Likely cause (AI explanation):** Battery voltage (89% of the result)
- **What needs to change:** Battery voltage has to come down from 15.3 V to about 14.7 V (healthy range 13.6-14.4 V)
- **What to do now:**
  - Voltage is too high (possible overcharging). This can damage the battery and electronics; get the charging system checked as soon as possible.
  - Have the battery, alternator and voltage regulator tested; the voltage reading is driving this result.
  - Have the battery and alternator (charging unit) tested at a garage.
  - Check that the battery terminals are tight and free of white or green corrosion.
  - Avoid using many electrical items (A/C, lights, audio) at the same time until it is checked.
  - Repair target: Battery voltage has to come down from 15.3 V to about 14.7 V (healthy range 13.6-14.4 V). Take a new reading after the repair to confirm.
- **To make it last:**
  - Clean the battery terminals every few months.
  - Avoid many very short trips; they do not give the battery time to recharge.
  - Replace the battery every 3-4 years or when a test shows it is weak.
  - Have the alternator belt checked at every service.

<sub>Answer key (researcher only): problem = Battery / charging system; recommended decision = Negotiate and repair the named part</sub>

---

## S2: Short test drive in town

| Reading | Value |
|---|---|
| Engine speed | 900 rpm |
| Engine load | 20 % |
| Coolant temperature | 88 °C |
| Battery voltage | 12.50 V |

### Version A (scanner)

**Trouble codes:** No trouble codes stored.

### Version B (prediction)

**Result:** Fault detected

- **Charging System Warning**, confidence 100%, severity Medium

### Version C (explainable system)

**Charging System Warning**, confidence 100%, severity Medium (act: Soon (within 3-7 days))
- **Likely cause (AI explanation):** Battery voltage (88% of the result)
- **What needs to change:** Battery voltage has to come up from 12.5 V to about 13.4 V (healthy range 13.6-14.4 V)
- **What to do now:**
  - Have the battery, alternator and voltage regulator tested; the voltage reading is driving this result.
  - Have the battery and alternator (charging unit) tested at a garage.
  - Check that the battery terminals are tight and free of white or green corrosion.
  - Avoid using many electrical items (A/C, lights, audio) at the same time until it is checked.
  - Repair target: Battery voltage has to come up from 12.5 V to about 13.4 V (healthy range 13.6-14.4 V). Take a new reading after the repair to confirm.
- **To make it last:**
  - Clean the battery terminals every few months.
  - Avoid many very short trips; they do not give the battery time to recharge.
  - Replace the battery every 3-4 years or when a test shows it is weak.
  - Have the alternator belt checked at every service.

<sub>Answer key (researcher only): problem = Battery / charging system; recommended decision = Negotiate and repair the named part</sub>

---

## S3: After a 20-minute drive

| Reading | Value |
|---|---|
| Engine speed | 1800 rpm |
| Engine load | 45 % |
| Coolant temperature | 104 °C |
| Battery voltage | 14.00 V |
| Vibration (x / y / z) | 0.05 / 0.04 / 0.06 g |

### Version A (scanner)

**Trouble codes:** No trouble codes stored.

### Version B (prediction)

**Result:** Fault detected

- **Cooling System Warning**, confidence 99%, severity High

### Version C (explainable system)

**Cooling System Warning**, confidence 99%, severity High (act: Immediately (within 1-2 days))
- **Likely cause (AI explanation):** Engine temperature (78% of the result)
- **What needs to change:** Engine temperature has to come down from 104 °C to about 98 °C (healthy range 80-96 °C)
- **What to do now:**
  - Check the coolant level, radiator fan and thermostat; the engine temperature is driving this result.
  - If the temperature gauge is high, stop in a safe place and switch off the engine.
  - Do not open the radiator cap while the engine is hot.
  - When the engine is cool, check the coolant level and look for leaks under the car.
  - Have the radiator, thermostat, cooling fan and water pump inspected before long drives.
  - Repair target: Engine temperature has to come down from 104 °C to about 98 °C (healthy range 80-96 °C). Take a new reading after the repair to confirm.
- **To make it last:**
  - Use the coolant type recommended for your vehicle, not plain water.
  - Replace the coolant at the interval in the owner's manual (usually every 2-3 years).
  - Keep the radiator front clean from dust and leaves.
  - Watch the temperature gauge in heavy traffic and on hills.

<sub>Answer key (researcher only): problem = Cooling system; recommended decision = Get a full inspection before buying</sub>

---

## S4: Highway speed

| Reading | Value |
|---|---|
| Engine speed | 3400 rpm |
| Engine load | 25 % |
| Coolant temperature | 84 °C |
| Battery voltage | 14.00 V |
| Vibration (x / y / z) | -0.30 / 0.30 / -0.10 g |

### Version A (scanner)

**Trouble codes:** No trouble codes stored.

### Version B (prediction)

**Result:** Fault detected

- **Unusual Pattern Detected (Possible Hidden Fault)**, severity Low

### Version C (explainable system)

**Unusual Pattern Detected (Possible Hidden Fault): likely cause engine vibration**, severity Low (act: Plan soon (within 1-2 weeks))
- **Likely cause (AI explanation):** Engine vibration (66% of the result)
- **What needs to change:** Engine vibration has to come down from 0.44 g to about 0.23 g (healthy range 0.08-0.37 g)
- **What to do now:**
  - Have the engine mounts, spark plugs and ignition coils checked; engine vibration is driving this result.
  - Take another reading to see if the pattern repeats.
  - If it repeats, have the vehicle scanned at a garage.
  - Repair target: Engine vibration has to come down from 0.44 g to about 0.23 g (healthy range 0.08-0.37 g). Take a new reading after the repair to confirm.
- **To make it last:**
  - Run regular checks so changes are spotted early.
  - Follow the service schedule in the owner's manual.

<sub>Answer key (researcher only): problem = Engine mounts / ignition (vibration); recommended decision = Negotiate and repair the named part</sub>

---

## S5: Healthy car, normal driving

| Reading | Value |
|---|---|
| Engine speed | 1800 rpm |
| Engine load | 45 % |
| Coolant temperature | 88 °C |
| Battery voltage | 14.10 V |
| Vibration (x / y / z) | 0.05 / 0.04 / 0.06 g |

### Version A (scanner)

**Trouble codes:** No trouble codes stored.

### Version B (prediction)

**Result:** No fault found.

### Version C (explainable system)

**Result:** No fault found.

<sub>Answer key (researcher only): problem = No problem; recommended decision = Buy</sub>

---

## S6: Climbing a hill, heavily loaded

| Reading | Value |
|---|---|
| Engine speed | 2689 rpm |
| Engine load | 80 % |
| Coolant temperature | 97 °C |
| Battery voltage | 13.73 V |
| Vibration (x / y / z) | 0.10 / 0.24 / -0.01 g |

### Version A (scanner)

**Trouble codes:** No trouble codes stored.

### Version B (prediction)

**Result:** Fault detected

- **Engine Abnormality Suspected**, confidence 94%, severity Medium

### Version C (explainable system)

**Engine Abnormality Suspected**, confidence 94%, severity Medium (act: Soon (within 3-7 days))
- ⚠️ **Low reliability:** The AI decision is driven by engine load, not by engine speed (rpm) or engine temperature, so the reading may be outside what the model learned.
- **Likely cause (AI explanation):** Engine load (65% of the result)
- **What needs to change:** Battery voltage has to come up from 13.7 V to about 13.8 V (healthy range 13.6-14.4 V)
- **What to do now:**
  - Avoid heavy loads and hard acceleration until it is checked; the engine load is driving this result.
  - Have the engine scanned for fault codes at a garage.
  - Have the spark plugs, ignition coils and fuel injectors checked.
  - Avoid hard acceleration and heavy loads until it is checked.
  - Repair target: Battery voltage has to come up from 13.7 V to about 13.8 V (healthy range 13.6-14.4 V). Take a new reading after the repair to confirm.
- **To make it last:**
  - Use good-quality fuel from reliable stations.
  - Replace spark plugs and the air filter on schedule.
  - Let the engine idle smoothly for a short time after a cold start before driving hard.
  - Do not ignore shaking, rough idling or loss of power; check them early.

<sub>Answer key (researcher only): problem = No problem (warm engine under heavy load); recommended decision = Take another reading before deciding</sub>

---
