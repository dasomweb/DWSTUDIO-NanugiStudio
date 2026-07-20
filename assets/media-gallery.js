import { Component } from '@theme/component';
import { ThemeEvents, VariantUpdateEvent, ZoomMediaSelectedEvent } from '@theme/events';

/**
 * A custom element that renders a media gallery.
 *
 * @typedef {object} Refs
 * @property {import('./zoom-dialog').ZoomDialog} [zoomDialogComponent] - The zoom dialog component.
 * @property {import('./slideshow').Slideshow} [slideshow] - The slideshow component.
 * @property {HTMLElement[]} [media] - The media elements.
 *
 * @extends Component<Refs>
 */
export class MediaGallery extends Component {
  connectedCallback() {
    super.connectedCallback();

    const { signal } = this.#controller;
    const target = this.closest('.shopify-section, dialog');

    target?.addEventListener(ThemeEvents.variantUpdate, this.#handleVariantUpdate, { signal });
    this.refs.zoomDialogComponent?.addEventListener(ThemeEvents.zoomMediaSelected, this.#handleZoomMediaSelected, {
      signal,
    });
  }

  #controller = new AbortController();

  disconnectedCallback() {
    super.disconnectedCallback();

    this.#controller.abort();
  }

  /**
   * Handles a variant update event by replacing the current media gallery with a new one.
   *
   * @param {VariantUpdateEvent} event - The variant update event.
   */
  #handleVariantUpdate = (event) => {
    // 변형에 연결된 대표 미디어(색상 칩)가 있으면 갤러리를 통째로 교체하지 않고
    // 그 슬라이드로 이동만 한다. 서버 재렌더 교체는 selected_or_first_available_variant 로
    // 렌더돼 첫 로드에도 첫 변형 칩이 히어로가 되는 문제가 있다. select 방식이면
    // 첫 화면은 대표이미지가 유지되고, 색상 클릭 시에만 그 칩으로 넘어간다.
    const mediaId = event.detail?.resource?.featured_media?.id;

    if (mediaId != null) {
      const mediaEls = Array.from(this.media ?? []);
      const index = mediaEls.findIndex((el) => String(el.dataset.mediaId) === String(mediaId));

      if (index >= 0) {
        this.slideshow?.select(index, undefined, { animate: false });
        return;
      }
    }

    // 폴백: 변형에 대표 미디어가 없거나 갤러리에서 못 찾으면 기존 교체 로직을 쓴다.
    const source = event.detail.data.html;

    if (!source) return;
    const newMediaGallery = source.querySelector('media-gallery');

    if (!newMediaGallery) return;

    this.replaceWith(newMediaGallery);
  };

  /**
   * Handles the 'zoom-media:selected' event.
   * @param {ZoomMediaSelectedEvent} event - The zoom-media:selected event.
   */
  #handleZoomMediaSelected = async (event) => {
    this.slideshow?.select(event.detail.index, undefined, { animate: false });
  };

  /**
   * Zooms the media gallery.
   *
   * @param {number} index - The index of the media to zoom.
   * @param {PointerEvent} event - The pointer event.
   */
  zoom(index, event) {
    this.refs.zoomDialogComponent?.open(index, event);
  }

  /**
   * Preloads an image.
   * @param {number} index - The index of the media to preload.
   */
  preloadImage(index) {
    const zoomDialogMedia = this.refs.zoomDialogComponent?.refs.media[index];
    if (!zoomDialogMedia) return;

    this.refs.zoomDialogComponent?.loadHighResolutionImage(zoomDialogMedia);
  }

  get slideshow() {
    return this.refs.slideshow;
  }

  get media() {
    return this.refs.media;
  }

  get presentation() {
    return this.dataset.presentation;
  }
}

if (!customElements.get('media-gallery')) {
  customElements.define('media-gallery', MediaGallery);
}
