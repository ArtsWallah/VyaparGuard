export type CachedImage = {
    uri: string;
    base64?: string | null;
    fileName?: string | null;
    mimeType?: string | null;
    fileSize?: number;
};

let activeCapturedImage: CachedImage | null = null;

export function setCapturedImage(image: CachedImage | null) {
    activeCapturedImage = image;
}

export function getCapturedImage(): CachedImage | null {
    return activeCapturedImage;
}

export function clearCapturedImage() {
    activeCapturedImage = null;
}
