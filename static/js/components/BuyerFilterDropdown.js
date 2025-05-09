// BuyerFilterDropdown.js - Reusable buyer filter dropdown component

// Add component-specific styles
(function() {
    const style = document.createElement('style');
    style.textContent = `
        .dropdown-menu {
            max-width: 100%;
        }
        .form-check {
            margin-bottom: 0.5rem;
            padding-left: 2rem;
        }
        .form-floating .dropdown button {
            height: calc(3.5rem + 2px);
            line-height: 1.25;
            padding: 1rem 0.75rem;
        }
        .form-floating label {
            padding: 1rem 0.75rem;
        }
        .badge {
            margin-right: 5px;
        }
        .buyer-count {
            margin-right: 1.5rem;
        }
        .chevron-position {
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
        }
        .dropdown-toggle:hover, .btn-outline-secondary:hover {
            background-color: var(--bs-primary) !important;
            border-color: var(--bs-primary) !important;
            color: white !important;
        }
        .form-check-input:checked {
            background-color: var(--bs-primary);
            border-color: var(--bs-primary);
        }
    `;
    document.head.appendChild(style);
})();

Vue.component('buyer-filter-dropdown', {
    template: `
        <div class="form-floating mb-3">
            <div class="dropdown">
                <button class="btn btn-outline-secondary dropdown-toggle w-100 position-relative" 
                        type="button" 
                        id="buyerFilterDropdown" 
                        data-bs-toggle="dropdown" 
                        aria-expanded="false">
                        <span class="buyer-count">Wybierz kupujących ({{selectedIds.length}}/{{buyers.length}})</span>
                        <span class="chevron-position"></span>
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
