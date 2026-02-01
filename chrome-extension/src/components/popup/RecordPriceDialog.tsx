import React, { useCallback, useEffect, useState } from "react";
import type {
  ApiResponse,
  GlobalPartRead,
  Retailer,
  ScrapedProductData,
} from "../../types";

interface RecordPriceDialogProps {
  existingPart: GlobalPartRead;
  scrapedData: ScrapedProductData;
  retailer: Retailer | null;
  onClose: () => void;
  onPriceRecorded: () => void;
  sendMessage: (message: {
    action: string;
    listingData?: {
      global_part_id: number;
      retailer_id: number;
      product_url?: string;
      price_cents?: number;
    };
    domain?: string;
    sourceUrls?: string[];
    partId?: number;
    fileKeys?: string[];
    imageUrl?: string;
  }) => Promise<unknown>;
}

const RecordPriceDialog: React.FC<RecordPriceDialogProps> = ({
  existingPart,
  scrapedData,
  retailer,
  onClose,
  onPriceRecorded,
  sendMessage,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [uncachedUrls, setUncachedUrls] = useState<string[]>([]);
  const [selectedUrls, setSelectedUrls] = useState<string[]>([]);
  const [isCheckingImages, setIsCheckingImages] = useState(true);

  // Check which scraped images are not yet in our cache (max 10 per global part)
  useEffect(() => {
    const urls = (scrapedData.image_urls ?? []).slice(0, 10);
    if (urls.length === 0) {
      setIsCheckingImages(false);
      return;
    }
    (async () => {
      const response = (await sendMessage({
        action: "checkUncachedImageUrls",
        sourceUrls: urls,
      })) as ApiResponse<{ uncachedUrls: string[] }>;
      if (response.success && response.data) {
        setUncachedUrls(response.data.uncachedUrls);
        setSelectedUrls(response.data.uncachedUrls);
      }
      setIsCheckingImages(false);
    })();
  }, [scrapedData.image_urls, sendMessage]);

  const toggleImage = useCallback((url: string) => {
    setSelectedUrls((prev) =>
      prev.includes(url) ? prev.filter((u) => u !== url) : [...prev, url]
    );
  }, []);

  const scrapedPriceCents = scrapedData.price;
  const scrapedPriceFormatted =
    scrapedPriceCents != null
      ? `$${(scrapedPriceCents / 100).toFixed(2)}`
      : "—";

  const handleRecordPrice = async () => {
    if (!retailer || scrapedPriceCents == null || scrapedPriceCents < 0) {
      setError("Unable to record price: retailer or price not available");
      return;
    }

    setError("");
    setIsLoading(true);

    try {
      // Upload selected uncached images and append to part (backend enforces max per global part)
      const maxImagesPerPart = 12; // must match backend MAX_IMAGES_PER_GLOBAL_PART
      const currentCount = existingPart.image_urls?.length ?? 0;
      const slotsLeft = Math.max(0, maxImagesPerPart - currentCount);

      if (selectedUrls.length > 0 && slotsLeft > 0) {
        const fileKeys: string[] = [];
        const urlsToUpload = selectedUrls.slice(0, slotsLeft);
        for (const url of urlsToUpload) {
          const uploadRes = (await sendMessage({
            action: "uploadImage",
            imageUrl: url,
            partId: existingPart.id,
          })) as ApiResponse<{ fileKey: string }>;
          if (uploadRes.success && uploadRes.data?.fileKey) {
            fileKeys.push(uploadRes.data.fileKey);
          } else {
            // Backend may reject when part is full (e.g. race); stop trying more
            break;
          }
        }
        if (fileKeys.length > 0) {
          const appendRes = (await sendMessage({
            action: "appendImagesToGlobalPart",
            partId: existingPart.id,
            fileKeys: fileKeys.slice(0, maxImagesPerPart),
          })) as ApiResponse<unknown>;
          if (!appendRes.success) {
            // Don't block price recording - user may lack edit permission
            console.warn("Append images failed:", appendRes.error);
          }
        }
      }

      const listingData: {
        global_part_id: number;
        retailer_id: number;
        product_url?: string;
        price_cents?: number;
      } = {
        global_part_id: existingPart.id,
        retailer_id: retailer.id,
        price_cents: scrapedPriceCents,
      };
      if (scrapedData.product_url?.trim()) {
        listingData.product_url = scrapedData.product_url.trim();
      }
      const response = (await sendMessage({
        action: "addPartListing",
        listingData,
      })) as ApiResponse<unknown>;

      if (response.success) {
        chrome.storage.sync.get(
          ["openPartAfterCreation", "openInNewTab", "apiUrl"],
          (settings) => {
            const shouldOpen = settings["openPartAfterCreation"] !== false;
            const openInNewTab = settings["openInNewTab"] !== false;

            if (shouldOpen) {
              const apiUrl =
                (settings["apiUrl"] as string) ||
                "https://api.carmodpicker.webbpulse.com/api";
              let frontendUrl = "https://carmodpicker.webbpulse.com";
              if (
                apiUrl.includes("localhost") ||
                apiUrl.includes("127.0.0.1")
              ) {
                frontendUrl = "http://localhost:4000";
              } else if (apiUrl.includes("staging")) {
                frontendUrl = "https://carmodpicker.staging.webbpulse.com";
              }
              const partUrl = `${frontendUrl}/global-parts/${existingPart.id}`;
              if (openInNewTab) {
                chrome.tabs.create({ url: partUrl });
              } else {
                chrome.tabs.query(
                  { active: true, currentWindow: true },
                  (tabs) => {
                    if (tabs[0]?.id) {
                      chrome.tabs.update(tabs[0].id, { url: partUrl });
                    }
                  }
                );
              }
            }
          }
        );
        onPriceRecorded();
      } else {
        setError(response.error || "Failed to record price");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record price");
    } finally {
      setIsLoading(false);
    }
  };

  const canRecordPrice =
    retailer != null && scrapedPriceCents != null && scrapedPriceCents >= 0;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-neutral-900/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl w-full max-w-[600px] max-h-[90vh] flex flex-col my-4">
        <div className="shrink-0 p-6 border-b border-white/10">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold text-gradient">
              Part Already in Catalog
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="text-neutral-400 hover:text-white text-2xl leading-none p-2 hover:bg-white/10 rounded-xl transition-all duration-300"
              aria-label="Close dialog"
            >
              &times;
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6 overflow-y-auto flex-1 min-h-0">
          <p className="text-neutral-300 text-sm">
            This product URL is already in the CarModPicker catalog. Scraping
            again is used to record an updated price for price history tracking.
          </p>

          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-xl text-red-200 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-4 p-4 rounded-xl bg-white/5 border border-white/10">
            <div>
              <span className="text-xs text-neutral-500 uppercase tracking-wide">
                Part
              </span>
              <p className="text-white font-medium">{existingPart.name}</p>
              {existingPart.part_number && (
                <p className="text-neutral-400 text-sm">
                  Part #: {existingPart.part_number}
                </p>
              )}
            </div>

            <div>
              <span className="text-xs text-neutral-500 uppercase tracking-wide">
                Current scraped price
              </span>
              <p className="text-white text-lg font-semibold">
                {scrapedPriceFormatted}
              </p>
            </div>

            {scrapedPriceCents == null && (
              <div className="p-3 bg-amber-500/20 border border-amber-500/50 rounded-lg text-amber-200 text-sm">
                No price was found on the page. Unable to record price.
              </div>
            )}

            {retailer ? (
              <div>
                <span className="text-xs text-neutral-500 uppercase tracking-wide">
                  Retailer
                </span>
                <p className="text-white">{retailer.name}</p>
              </div>
            ) : (
              <div className="p-3 bg-amber-500/20 border border-amber-500/50 rounded-lg text-amber-200 text-sm">
                Retailer not found for this domain. Price cannot be recorded.
                You can still view the part in the catalog.
              </div>
            )}
          </div>

          {/* New images not yet in catalog */}
          {uncachedUrls.length > 0 && (
            <div className="space-y-3 p-4 rounded-xl bg-white/5 border border-white/10">
              <div>
                <span className="text-xs text-neutral-500 uppercase tracking-wide">
                  New images (not in catalog)
                </span>
                <p className="text-neutral-400 text-sm mt-1">
                  {selectedUrls.length} of {uncachedUrls.length} selected to
                  add. Click × to exclude, click again to include.
                </p>
              </div>
              {isCheckingImages ? (
                <p className="text-neutral-500 text-sm">Checking images…</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {uncachedUrls.map((url) => (
                    <div
                      key={url}
                      className={`relative group ${
                        selectedUrls.includes(url) ? "" : "opacity-40"
                      }`}
                    >
                      <img
                        src={url}
                        alt=""
                        className="w-16 h-16 object-cover rounded border border-white/20"
                        onError={(e) => {
                          e.currentTarget.style.display = "none";
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => toggleImage(url)}
                        className={`absolute -top-1 -right-1 w-5 h-5 rounded-full bg-neutral-800 border border-white/30 flex items-center justify-center text-white text-sm hover:bg-red-600 transition-colors ${
                          selectedUrls.includes(url)
                            ? "opacity-100"
                            : "opacity-50 line-through"
                        }`}
                        title={
                          selectedUrls.includes(url)
                            ? "Exclude from upload"
                            : "Include in upload"
                        }
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-3 px-6 rounded-xl font-semibold bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white transition-all duration-300 hover:bg-white/20 disabled:opacity-50"
              disabled={isLoading}
            >
              Close
            </button>
            <button
              type="button"
              onClick={handleRecordPrice}
              className="flex-1 py-3 px-6 rounded-xl font-semibold bg-linear-to-r from-[#667eea] to-[#764ba2] text-white transition-all duration-300 hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isLoading || !canRecordPrice}
            >
              {isLoading ? "Recording..." : "Record Price"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RecordPriceDialog;
