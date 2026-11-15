/**
 * Photography used across the site. All photos are from Unsplash and free to use under the
 * Unsplash License (https://unsplash.com/license). They load from the Unsplash CDN in the visitor's
 * browser. To self-host, download them into /public/images and change the `src` values.
 * Every image has a colour fallback, so pages stay readable if a photo cannot load.
 */
const u = (id: string, w = 2000) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${w}&q=70`;

export const IMAGES = {
  heroWheat: {
    src: u("photo-1609130825188-a66b4aef2278", 2400),
    alt: "Green wheat ears in a field under a blue sky",
    credit: "Beth Macdonald / Unsplash",
    page: "https://unsplash.com/photos/green-wheat-field-during-daytime-zsvnVQOAnDc",
  },
  youngWheat: {
    src: u("photo-1624818988460-062e9ec73186", 1600),
    alt: "Young wheat growing in a farmer's field",
    credit: "Matt Seymour / Unsplash",
    page: "https://unsplash.com/photos/green-wheat-in-close-up-photography-ie-1Ta9Cg7M",
  },
  irrigation: {
    src: u("photo-1738598665698-7fd7af4b5e0c", 1600),
    alt: "Two sprinklers watering a maize field",
    credit: "Being Organic in EU / Unsplash",
    page: "https://unsplash.com/photos/two-sprinklers-spraying-water-on-a-corn-field-ZYiOik4jels",
  },
  soilHands: {
    src: u("photo-1709633644385-e4e51e5646f1", 1400),
    alt: "A farmer in India holding a handful of soil",
    credit: "Unsplash",
    page: "https://unsplash.com/photos/a-woman-holding-a-handful-of-dirt-in-her-hands-qqRl8fd7Rxs",
  },
  aerial: {
    src: u("photo-1724391381933-82aa1c3e8a56", 2000),
    alt: "Farm fields seen from an aircraft window",
    credit: "Unsplash",
    page: "https://unsplash.com/photos/a-view-of-a-field-from-a-plane-window-BsCaUCBcs5U",
  },
} as const;

export type ImageKey = keyof typeof IMAGES;
