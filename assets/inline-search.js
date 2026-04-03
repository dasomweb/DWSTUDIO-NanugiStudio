class InlineSearch extends HTMLElement {
  constructor() {
    super();
    this.input = this.querySelector('[data-inline-search-input]');
    this.dropdown = this.querySelector('[data-inline-search-dropdown]');
    this.sectionId = this.dataset.sectionId;
    this.debounceTimer = null;

    this.input.addEventListener('input', this.onInput.bind(this));
    this.input.addEventListener('focus', this.onFocus.bind(this));
    document.addEventListener('click', this.onClickOutside.bind(this));
    this.input.addEventListener('keydown', this.onKeyDown.bind(this));
  }

  onInput() {
    clearTimeout(this.debounceTimer);
    const query = this.input.value.trim();

    if (query.length < 2) {
      this.close();
      return;
    }

    this.debounceTimer = setTimeout(() => {
      this.fetchResults(query);
    }, 200);
  }

  onFocus() {
    if (this.input.value.trim().length >= 2 && this.dropdown.innerHTML.trim()) {
      this.open();
    }
  }

  onClickOutside(e) {
    if (!this.contains(e.target)) {
      this.close();
    }
  }

  onKeyDown(e) {
    if (e.key === 'Escape') {
      this.close();
      this.input.blur();
    }
  }

  async fetchResults(query) {
    try {
      const url = `${Theme.routes.predictive_search_url}?q=${encodeURIComponent(query)}&resources[type]=product&resources[limit]=10&section_id=${this.sectionId}`;
      const response = await fetch(url);
      if (!response.ok) return;

      const text = await response.text();
      const html = new DOMParser().parseFromString(text, 'text/html');
      const results = html.querySelector(`#shopify-section-${this.sectionId}`);

      if (results) {
        this.dropdown.innerHTML = results.innerHTML;
        this.open();
      }
    } catch (err) {
      // silently fail
    }
  }

  open() {
    this.dropdown.hidden = false;
    this.dataset.open = '';
  }

  close() {
    this.dropdown.hidden = true;
    delete this.dataset.open;
  }
}

if (!customElements.get('inline-search')) {
  customElements.define('inline-search', InlineSearch);
}
