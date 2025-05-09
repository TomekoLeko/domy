// BuyerFilterDropdown.js - Reusable buyer filter dropdown component
Vue.component('buyer-filter-dropdown', {
    template: `
        <div class="form-floating mb-3" style="border: 2px solid blue;">
            <div class="dropdown">
                <button class="btn btn-outline-secondary dropdown-toggle w-100 d-flex justify-content-between align-items-center" 
                        type="button" 
                        id="buyerFilterDropdown" 
                        data-bs-toggle="dropdown" 
                        aria-expanded="false">
                    <span>Wybierz kupujących ({{selectedIds.length}}/{{buyers.length}})</span>
                    <span class="badge bg-primary">{{selectedIds.length}}</span>
                </button>
                <div class="dropdown-menu w-100 p-3" aria-labelledby="buyerFilterDropdown">
                    <div class="mb-2">
                        <div class="d-flex justify-content-between">
                            <button class="btn btn-sm btn-outline-secondary" @click="selectAll">Zaznacz wszystkich</button>
                            <button class="btn btn-sm btn-outline-secondary" @click="deselectAll">Odznacz wszystkich</button>
                        </div>
                    </div>
                    <div class="overflow-auto" style="max-height: 300px;">
                        <div class="form-check" v-for="buyer in buyers">
                            <input class="form-check-input" type="checkbox" 
                                :id="'buyer-' + buyer.id" 
                                :value="buyer.id" 
                                v-model="selectedIds">
                            <label class="form-check-label" :for="'buyer-' + buyer.id">{{ buyer.name }}</label>
                        </div>
                    </div>
                </div>
            </div>
            <label for="buyerFilterDropdown">Kupujący</label>
        </div>
    `,
    props: {
        value: {
            type: Array,
            required: true
        },
        buyers: {
            type: Array,
            required: true
        }
    },
    computed: {
        selectedIds: {
            get() {
                return this.value;
            },
            set(value) {
                this.$emit('input', value);
            }
        }
    },
    methods: {
        selectAll() {
            this.$emit('select-all');
        },
        deselectAll() {
            this.$emit('deselect-all');
        }
    }
}); 
