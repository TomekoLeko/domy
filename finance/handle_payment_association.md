# Spis: przypisywanie płatności do zamówień / pozycji oraz „ile zostało do zapłaty”

Dokument pomocniczy przed przebudową na **`SettlementAllocation`** (`finance.models.SettlementAllocation`: `payment`, `order_item`, `allocated_amount`).

Poniżej: wyłącznie miejsca istotne dla **powiązania `Payment` ↔ `Order` / `OrderItem`** albo **wyliczenia pozostałości (`left_to_pay`, sumy dla kupującego, status rozliczenia)**.  
Dla każdej pozycji: **`Teraz:`** obecne zachowanie, **`Chcemy:`** docelowy kierunek (jawne alokacje przez `SettlementAllocation`, spójna walidacja sum alokacji względem `Payment.amount` i pozostałości na pozycji).

**Numeracja:** sprawy do przebudowy w kodzie — **#2–#19**; kroki migracji / porządku danych na końcu — **M.1–M.4** (nie są osobnymi endpointami).

---

## Uwaga: M2M a `SettlementAllocation` (stan na dziś)

**Uwaga:** M2M **`Payment.related_order_items` nie został usunięty** — **na razie współistnieje** z nową tabelą **`SettlementAllocation`**. Kolejne kroki to: **migracja danych** (np. wygenerowanie wierszy alokacji z istniejących powiązań M2M), **podmiana logiki** w kodzie zgodnie z tym spisem (endpoint po endpoincie / warstwa modelu), a dopiero potem — jeśli zdecydujecie — **usunięcie** pola M2M `related_order_items` po pełnym przełączeniu odczytów i zapisów (osobna migracja Django).

Do czasu tej przebudowy **źródłem prawdy dla rozliczeń w kodzie nadal jest M2M + heurystyki** (`left_to_pay`, kontrybucje itd.); tabela `SettlementAllocation` jest przygotowana pod docelowy model — **nie należy zakładać**, że samo jej istnienie zmienia zachowanie API bez dalszych zmian w widokach i właściwościach modeli.

---

## Endpointy `api_*` — `finance/views.py`

### #2 — `api_create_payment`

**Teraz:** Dla `payment_type == 'order'` tworzy jeden `Payment` z `related_order` i **`related_order_items.set(buyer_items)`** (wszystkie pozycje, gdzie `buyer_id == order.buyer_id`). Walidacja kwoty względem `_order_buyer_left_to_pay_total` (suma `OrderItem.left_to_pay`). Po zapisie: `Order.update_payment_status_from_settlement()`.

**Chcemy:** Tworzenie płatności + **jawne wiersze `SettlementAllocation`** (lista par `order_item` + `allocated_amount` lub reguła generująca alokacje), walidacja `sum(allocated_amount) == payment.amount` (lub ≤ z jasną polityką nadpłat), powiązanie z zamówieniem bez konieczności utrzymywania równoległego M2M (lub M2M wyłącznie jako cache/legacy do usunięcia w kolejnym kroku).

---

### #3 — `api_delete_contribution`

**Teraz:** Usuwa `Payment` typu `contribution` tylko jeśli **brak** `related_order` i **brak** powiązanych `related_order_items`.

**Chcemy:** Warunek usuwania oparty o **brak `SettlementAllocation`** (oraz innych twardych reguł biznesowych); ewentualnie migracja danych z M2M do alokacji przed przełączeniem guardów.

---

### #4 — `api_delete_payment`

**Teraz:** Usuwa dowolny `Payment`; jeśli był `related_order`, ponownie ładuje zamówienie i wywołuje `update_payment_status_from_settlement()`. Usunięcie kaskadowe M2M jest po stronie Django.

**Chcemy:** Usunięcie płatności kaskaduje **`SettlementAllocation`** (FK `CASCADE` już na modelu); status zamówienia liczony z alokacji / `left_to_pay` opartego na sumach `allocated_amount`.

---

### #5 — `api_get_filtered_orders`

**Teraz:** Alias do `get_filtered_orders`: dla zamówień z filtrów sumuje **`item.left_to_pay`** po pozycjach z `item.buyer_id == order.buyer_id`, zwraca `left_to_pay` w JSON dla formularza Rozliczenia.

**Chcemy:** Ta sama semantyka odpowiedzi, ale `OrderItem.left_to_pay` (i ewentualnie sumy po zamówieniu) liczone z **`sum(SettlementAllocation.allocated_amount)`** (oraz ewentualnie spójny fallback przy migracji).

---

### #6 — `api_get_or_create_monthly_usage_for_buyer`

**Teraz:** Zwraca `MonthlyContributionUsage` i listę `order_item_ids` z **M2M `usage.order_items`** — to **nie** jest bezpośrednio `Payment` ↔ `OrderItem`, lecz limit miesięczny / pozycje „przypięte” do profilu beneficjenta po kontrybucjach.

**Chcemy:** Jeśli logika miesięczna ma pozostać powiązana z tymi samymi pozycjami co rozliczenia, ujednolicić źródło prawdy (np. nadal M2M usage **albo** odczyt z alokacji kontrybucji — decyzja produktowa); ten endpoint **nie musi** duplikować `SettlementAllocation`, ale trzeba sprawdzić spójność po zmianie przypisywania kontrybucji.

---

### #7 — `api_get_contributors` / `api_get_filtered_users` / `api_list_payments`

**Teraz:** Nie przypisują płatności do pozycji ani nie liczą `left_to_pay` dla zamówień (lista płatności nie serializuje `related_order_items` w `_serialize_payment_list_row`).

**Chcemy:** Opcjonalnie rozszerzyć `api_list_payments` o zwięzłą reprezentację alokacji (id pozycji + kwoty) do podglądu staff — poza zakresem samej migracji modelu.

---

## Endpointy `api_*` — `products/views.py`

### #8 — `api_delete_order`

**Teraz:** Przed usunięciem zamówienia znajduje `Payment` z M2M `related_order_items` przecinającym się z pozycjami zamówienia i wykonuje **`payment.related_order_items.remove(*order_items)`**.

**Chcemy:** Usunięcie / oderwanie alokacji (`SettlementAllocation` dla tych pozycji lub CASCADE przy usuwaniu `OrderItem` — już przy `ForeignKey(..., CASCADE)` na `order_item`); upewnić się, że płatności „gołe” mają sensowną politykę (np. `related_order` null + ostrzeżenie).

---

### #9 — `api_list_of_orders_for_buyer`

**Teraz:** Dla każdej pozycji zwraca **`left_to_pay`** z właściwości `OrderItem`; sumuje **`left_to_pay_buyer`** dla pozycji, gdzie `item.buyer_id == buyer`.

**Chcemy:** Identyczny kontrakt API, ale `left_to_pay` wyliczane z **`SettlementAllocation`** (i ewentualnie krótki okres podwójnego źródła prawdy przy migracji).

---

### #10 — `api_list_of_orders_for_admin`

**Teraz:** Jak wyżej — **`left_to_pay`** per pozycja w payloadzie (bez sumy „buyer” w głównym obiekcie zamówienia w tym widoku).

**Chcemy:** Jak wyżej — spójne liczenie z alokacji.

---

### #11 — `api_create_order`

**Teraz:** Tworzy zamówienie i pozycje; zwraca `payment_status` z modelu (domyślnie `pending`), **bez** tworzenia płatności ani alokacji.

**Chcemy:** Bez zmian w przypisywaniu płatności; ewentualnie tylko dopisek w dokumentacji API, że rozliczenie następuje osobnymi endpointami finansowymi.

---

## Widoki powiązane (bez prefiksu `api_` w nazwie), ale używane z frontu / ścieżek `api/`

### #12 — `get_filtered_orders` (`finance/views.py`, to samo co `api_get_filtered_orders`)

**Teraz / Chcemy:** Jak **#5** (`api_get_filtered_orders`) — ta sama implementacja / ten sam zakres zmian w kodzie.

---

### #13 — `assign_payment_to_item` (`POST …/finance/assign-payment-to-item/`)

**Teraz:** `payment.related_order_items.add(order_item)` + `order_item.order.update_payment_status_from_settlement()`.

**Chcemy:** Tworzenie / aktualizacja **`SettlementAllocation`** (z walidacją kwoty względem `Payment.amount` i pozostałości na pozycji), potem przeliczenie statusu zamówienia; M2M opcjonalnie do usunięcia.

---

### #14 — `get_available_contributions` / `get_all_contributions` (`finance/views.py`)

**Teraz:** Odczyt listy kontrybucji; w payloadzie **`related_order_items`** (serializacja pozycji). Dostępna kwota kontrybucji: m.in. **`Payment.available_amount`** (`amount - sum(price)` powiązanych pozycji) oraz zapytanie z adnotacją `Sum('related_order_items__price')`.

**Chcemy:** „Zużycie” i dostępność liczone z **`SettlementAllocation`** (suma `allocated_amount` dla danej płatności), spójnie z przypisaniami kontrybucji do zamówień.

---

### #15 — `delete_payment` (szablon Django `finance/payment/.../delete/`)

**Teraz:** Jak **#4** (`api_delete_payment`) — usuwa `Payment` i odświeża status zamówienia po `related_order`.

**Chcemy:** Jak **#4** — kaskada alokacji (`SettlementAllocation`).

---

## Funkcje pomocnicze / model (nie są endpointami, ale wpływają na „ile zostało”)

### #16 — `_order_buyer_left_to_pay_total(order)` — `finance/views.py`

**Teraz:** Suma **`item.left_to_pay`** po pozycjach z `item.buyer_id == order.buyer_id`.

**Chcemy:** Suma pozostałości z **`price - sum(allocations)`** dla tych pozycji (lub dalej przez właściwość `left_to_pay` zasilaną alokacjami).

---

### #17 — `Order.update_payment_status_from_settlement()` — `products/models.py`

**Teraz:** Na podstawie pozycji kupującego (`buyer_id == order.buyer_id`) sumuje `left_to_pay` / `price` i ustawia `payment_status` (`pending` / `partial` / `paid`).

**Chcemy:** Bez zmiany kontraktu metody — ale **`left_to_pay`** musi pochodzić z **`SettlementAllocation`** (+ ewentualnie M2M w fazie przejściowej).

---

### #18 — `OrderItem.sum_of_order_item_payments` / `left_to_pay` oraz `payment_amount_attributed_to_order_item` — `products/models.py`

**Teraz:** Rozbicie kwoty każdej płatności **proporcjonalnie do `price`** po zbiorze pozycji powiązanych M2M `payment.related_order_items`; suma po płatnościach → `left_to_pay`.

**Chcemy:** **`sum(SettlementAllocation.allocated_amount)`** dla `(order_item, payment)` lub prościej **`SettlementAllocation.objects.filter(order_item=self).aggregate(Sum('allocated_amount'))`** (z uwzględnieniem ewentualnych innych źródeł typu legacy M2M do czasu migracji).

---

### #19 — `Payment.available_amount` oraz `Payment.get_available_contributions` — `finance/models.py`

**Teraz:** Bazuje na **`sum(item.price)`** dla `related_order_items`.

**Chcemy:** `amount - sum(SettlementAllocation.allocated_amount)` dla danej płatności (lub równoważnie suma alokacji po wszystkich pozycjach).

---

## Uwagi na migrację kodu (M.*)

**M.1.** Stan współistnienia M2M i `SettlementAllocation`: **patrz sekcja „Uwaga: M2M a SettlementAllocation (stan na dziś)”** u góry dokumentu.

**M.2.** Dopóki istnieją dane tylko w M2M, migracja danych może wygenerować **`SettlementAllocation`** z obecnych powiązań (np. przy jednej pozycji: `allocated_amount = payment.amount`; przy wielu: proporcjonalnie jak dziś w kodzie, żeby nie zmienić sald).

**M.3.** **`related_order_items`** można planowo usunąć po pełnym przełączeniu odczytów/zapisów (osobna migracja i prompt) — dopiero po spełnieniu warunków z sekcji „Uwaga” powyżej.

**M.4.** **`MonthlyContributionUsage.order_items`** pozostaje osobnym bytem — nie mylić z `SettlementAllocation` (osobna ścieżka od przypisywania kontrybucji do pozycji zamówienia).
