# Spis: przypisywanie płatności do zamówień / pozycji oraz „ile zostało do zapłaty”

Dokument pomocniczy przed przebudową na **`SettlementAllocation`** (`finance.models.SettlementAllocation`: `payment`, `order_item`, `allocated_amount`).

Poniżej: wyłącznie miejsca istotne dla **powiązania `Payment` ↔ `Order` / `OrderItem`** albo **wyliczenia pozostałości (`left_to_pay`, sumy dla kupującego, status rozliczenia)**.  
Dla każdej pozycji: **`Teraz:`** obecne zachowanie, **`Chcemy:`** docelowy kierunek (jawne alokacje przez `SettlementAllocation`, spójna walidacja sum alokacji względem `Payment.amount` i pozostałości na pozycji).

**Numeracja:** sprawy do przebudowy w kodzie — **#13–#17** w liście poniżej (numery punktów bez przesuwania; **#4** — `MonthlyContributionUsage` z alokacji — zrealizowane; **#5** — `api_list_payments`: **`allocations`** — zrealizowane; **#6** — `api_delete_order` / `_delete_order_impl`: jawne **`SettlementAllocation.delete`** + M2M; **`related_order`** → SET_NULL — zrealizowane; **#7** — `api_list_of_orders_for_buyer` — zrealizowane; **#8** — `api_list_of_orders_for_admin` — zrealizowane; **#9** — `api_create_order` — zrealizowane; **#10** — `get_filtered_orders` / `api_get_filtered_orders` — zrealizowane; **#11** — `assign_payment_to_item` — zrealizowane; **#12** — `get_available_contributions` / `get_all_contributions` + `Payment.available_amount` / `get_available_contributions` (model) — zrealizowane).

**Commit:** po zrealizowaniu któregokolwiek zadania z tego spisu, w odpowiedzi / podsumowaniu dla autora **zaproponuj treść wiadomości commita po angielsku** (krótka, opisująca faktyczną zmianę; bez wstawiania jej do repozytorium, jeśli autor nie poprosi).

---

## Uwaga: M2M a `SettlementAllocation` (stan na dziś)

**Uwaga:** M2M **`Payment.related_order_items` nie został usunięty** — **na razie współistnieje** z tabelą **`SettlementAllocation`**. Kolejne kroki to **podmiana logiki** w kodzie zgodnie z tym spisem (endpoint po endpoincie / warstwa modelu), a na koniec — jeśli zdecydujecie — **usunięcie** pola M2M `related_order_items` po pełnym przełączeniu odczytów i zapisów (osobna migracja schematu Django).

Do czasu tej przebudowy część ścieżek w kodzie nadal używa M2M i heurystyk (`left_to_pay`, kontrybucje itd.); tabela `SettlementAllocation` jest przygotowana pod docelowy model — **nie należy zakładać**, że samo jej istnienie zmienia zachowanie API bez dalszych zmian w widokach i właściwościach modeli.

---

Przy usuwaniu poniższych nie zmieniaj numeracji.
Po wykonaniu zadania napisz propozyucje commitu po angielsku w oknie czatu. Oraz skasuj wykonane zadania z poniszej listy.

## Widoki powiązane (bez prefiksu `api_` w nazwie), ale używane z frontu / ścieżek `api/`

### #13 — `delete_payment` (szablon Django `finance/payment/.../delete/`)

**Teraz / Chcemy:** Wspólna logika z **`api_delete_payment`** w `finance/views.py`: usunięcie płatności (kaskada **`SettlementAllocation`** po FK), odświeżenie **`payment_status`** na każdym zamówieniu powiązanym przez `related_order`, **`SettlementAllocation`** lub M2M **`related_order_items`**.

---

## Funkcje pomocnicze / model (nie są endpointami, ale wpływają na „ile zostało”)

### #14 — `_order_buyer_left_to_pay_total(order)` — `finance/views.py`

**Teraz:** Suma **`item.left_to_pay`** po pozycjach z `item.buyer_id == order.buyer_id`.

**Chcemy:** Suma pozostałości z **`price - sum(allocations)`** dla tych pozycji (lub dalej przez właściwość `left_to_pay` zasilaną alokacjami).

---

### #15 — `Order.update_payment_status_from_settlement()` — `products/models.py`

**Teraz:** Na podstawie pozycji kupującego (`buyer_id == order.buyer_id`) sumuje `left_to_pay` / `price` i ustawia `payment_status` (`pending` / `partial` / `paid`).

**Chcemy:** Bez zmiany kontraktu metody — ale **`left_to_pay`** musi pochodzić z **`SettlementAllocation`** (+ ewentualnie M2M w fazie przejściowej w kodzie).

---

### #16 — `OrderItem.sum_of_order_item_payments` / `left_to_pay` oraz `payment_amount_attributed_to_order_item` — `products/models.py`

**Teraz:** Rozbicie kwoty każdej płatności **proporcjonalnie do `price`** po zbiorze pozycji powiązanych M2M `payment.related_order_items`; suma po płatnościach → `left_to_pay`.

**Chcemy:** **`sum(SettlementAllocation.allocated_amount)`** dla `(order_item, payment)` lub prościej **`SettlementAllocation.objects.filter(order_item=self).aggregate(Sum('allocated_amount'))`** (ewentualnie spójnie z M2M dopóki oba mechanizmy współistnieją w kodzie).

---

### #17 — `Payment.available_amount` oraz `Payment.get_available_contributions` — `finance/models.py`

**Teraz:** Bazuje na **`sum(item.price)`** dla `related_order_items`.

**Chcemy:** `amount - sum(SettlementAllocation.allocated_amount)` dla danej płatności (lub równoważnie suma alokacji po wszystkich pozycjach).

---
