
import { useState } from "react";
import {
    ActivityIndicator,
    Alert,
    Image,
    Platform,
    Pressable,
    ScrollView,
    StyleSheet,
    Text,
    View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as ImagePicker from "expo-image-picker";
import * as FileSystem from "expo-file-system/legacy";
import { router } from "expo-router";

const API_URL = "http://172.22.63.92:8000";

type SelectedImage = {
    uri: string;
    fileName?: string | null;
    mimeType?: string | null;
    fileSize?: number;
};

type ScanResponse = {
    schema_version?: string;
    file?: Record<string, unknown>;
    ocr?: Record<string, unknown>;
    image_quality?: Record<string, unknown>;
    forensics?: Record<string, unknown>;
    errors?: string[];
    verification?: Record<string, unknown>;
    detail?: string | { msg?: string }[];
};

export default function UploadScreen() {
    const [image, setImage] = useState<SelectedImage | null>(null);
    const [loading, setLoading] = useState(false);

    async function chooseImage() {
        try {
            const permission =
                await ImagePicker.requestMediaLibraryPermissionsAsync();

            if (!permission.granted) {
                Alert.alert(
                    "Permission required",
                    "Allow photo library access to select a payment screenshot."
                );
                return;
            }

            const result = await ImagePicker.launchImageLibraryAsync({
                mediaTypes: ["images"],
                allowsEditing: false,
                quality: 1,
            });

            if (result.canceled || !result.assets?.length) return;

            const asset = result.assets[0];

            setImage({
                uri: asset.uri,
                fileName: asset.fileName,
                mimeType: asset.mimeType,
                fileSize: asset.fileSize,
            });
        } catch (error) {
            Alert.alert(
                "Image selection failed",
                error instanceof Error ? error.message : "Please try again."
            );
        }
    }

    async function analyzeScreenshot() {
        if (!image?.uri) {
            Alert.alert("Select an image", "Choose a payment screenshot first.");
            return;
        }

        if (image.fileSize && image.fileSize > 10 * 1024 * 1024) {
            Alert.alert(
                "File too large",
                "The selected image exceeds the 10 MB processing limit. Please choose a smaller image."
            );
            return;
        }

        setLoading(true);

        try {
            // Give the multipart file part an explicit filename and MIME type.
            const extension = image.fileName?.split(".").pop()?.toLowerCase();
            const mimeType =
                image.mimeType ||
                (extension === "png" ? "image/png" : "image/jpeg");
            const filename =
                image.fileName || `payment-screenshot.${extension || "jpg"}`;

            let responseStatus: number;
            let responseText: string;

            if (Platform.OS !== "web") {
                try {
                    // Use native multipart uploader (handles content:// and file:// reliably)
                    const uploadResult = await FileSystem.uploadAsync(
                        `${API_URL}/api/v1/scan`,
                        image.uri,
                        {
                            httpMethod: "POST",
                            uploadType: FileSystem.FileSystemUploadType.MULTIPART,
                            fieldName: "image",
                            mimeType: mimeType,
                        }
                    );
                    responseStatus = uploadResult.status;
                    responseText = uploadResult.body;
                } catch {
                    // Fallback to fetch with FormData if uploadAsync encounters an issue
                    const formData = new FormData();
                    const filePart = {
                        uri: image.uri,
                        name: filename,
                        type: mimeType,
                    } as unknown as Blob;
                    formData.append("image", filePart);
                    formData.append("file", filePart);

                    const response = await fetch(`${API_URL}/api/v1/scan`, {
                        method: "POST",
                        body: formData,
                    });
                    responseStatus = response.status;
                    responseText = await response.text();
                }
            } else {
                // Web: convert local blob URI to real Blob
                const formData = new FormData();
                const imageFetch = await fetch(image.uri);
                const blob = await imageFetch.blob();
                formData.append("image", blob, filename);
                formData.append("file", blob, filename);

                const response = await fetch(`${API_URL}/api/v1/scan`, {
                    method: "POST",
                    body: formData,
                });
                responseStatus = response.status;
                responseText = await response.text();
            }

            let data: ScanResponse;

            try {
                data = JSON.parse(responseText) as ScanResponse;
            } catch {
                throw new Error(
                    `The server returned an invalid response (HTTP ${responseStatus}).`
                );
            }

            if (responseStatus < 200 || responseStatus >= 300) {
                const detail = data.detail;
                let message = `Request failed (HTTP ${responseStatus}).`;

                if (typeof detail === "string") {
                    message = detail;
                } else if (Array.isArray(detail)) {
                    message = detail
                        .map((item) =>
                            typeof item === "object" && item && "msg" in item
                                ? String(item.msg)
                                : String(item)
                        )
                        .join("\n");
                } else if (typeof detail === "object" && detail !== null) {
                    const detailObj = detail as Record<string, unknown>;
                    message = String(
                        detailObj.message ||
                        detailObj.msg ||
                        detailObj.detail ||
                        message
                    );
                }

                throw new Error(message);
            }

            router.push({
                pathname: "/result",
                params: {
                    result: encodeURIComponent(JSON.stringify(data)),
                },
            });
        } catch (error) {
            Alert.alert(
                "Analysis failed",
                error instanceof Error
                    ? `${error.message}\n\nCheck that the backend is running and your phone can reach ${API_URL}.`
                    : "Could not upload the screenshot. Please try again."
            );
        } finally {
            setLoading(false);
        }
    }

    return (
        <SafeAreaView style={styles.safeArea}>
            <ScrollView contentContainerStyle={styles.container}>
                <Pressable
                    onPress={() => router.back()}
                    style={styles.backButton}
                    accessibilityRole="button"
                >
                    <Text style={styles.backText}>‹ Back</Text>
                </Pressable>

                <Text style={styles.eyebrow}>VYAPARGUARD / SCANNER</Text>
                <Text style={styles.title}>Analyze payment screenshot</Text>
                <Text style={styles.description}>
                    Upload a payment screenshot to extract transaction details and
                    inspect possible image manipulation indicators.
                </Text>

                <View style={styles.uploadCard}>
                    {image ? (
                        <Image source={{ uri: image.uri }} style={styles.preview} />
                    ) : (
                        <View style={styles.placeholder}>
                            <Text style={styles.placeholderIcon}>▧</Text>
                            <Text style={styles.placeholderTitle}>
                                No screenshot selected
                            </Text>
                            <Text style={styles.placeholderDescription}>
                                Choose a PNG or JPEG image from your phone.
                            </Text>
                        </View>
                    )}

                    <Pressable
                        onPress={chooseImage}
                        disabled={loading}
                        style={({ pressed }) => [
                            styles.secondaryButton,
                            pressed && styles.pressed,
                            loading && styles.disabled,
                        ]}
                    >
                        <Text style={styles.secondaryButtonText}>
                            {image ? "Choose another image" : "Choose screenshot"}
                        </Text>
                    </Pressable>

                    {image?.fileName ? (
                        <Text style={styles.fileName} numberOfLines={2}>
                            {image.fileName}
                        </Text>
                    ) : null}
                </View>

                <Pressable
                    onPress={analyzeScreenshot}
                    disabled={!image || loading}
                    style={({ pressed }) => [
                        styles.primaryButton,
                        (!image || loading) && styles.disabled,
                        pressed && styles.pressed,
                    ]}
                >
                    {loading ? (
                        <View style={styles.loadingRow}>
                            <ActivityIndicator color="#FFFFFF" />
                            <Text style={styles.primaryButtonText}>Analyzing...</Text>
                        </View>
                    ) : (
                        <Text style={styles.primaryButtonText}>
                            Analyze screenshot →
                        </Text>
                    )}
                </Pressable>

                <View style={styles.notice}>
                    <Text style={styles.noticeTitle}>Important verification notice</Text>
                    <Text style={styles.noticeText}>
                        OCR reads text from an image, and forensic checks look for possible
                        manipulation indicators. Neither proves that money was received.
                        Always confirm payment in your bank or trusted transaction records.
                    </Text>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    safeArea: {
        flex: 1,
        backgroundColor: "#F7F8FA",
    },
    container: {
        padding: 22,
        paddingBottom: 40,
    },
    backButton: {
        alignSelf: "flex-start",
        paddingVertical: 8,
        paddingRight: 12,
        marginBottom: 22,
    },
    backText: {
        color: "#344054",
        fontSize: 16,
        fontWeight: "600",
    },
    eyebrow: {
        color: "#18794E",
        fontSize: 11,
        fontWeight: "800",
        letterSpacing: 1.5,
        marginBottom: 10,
    },
    title: {
        color: "#101828",
        fontSize: 28,
        lineHeight: 35,
        fontWeight: "800",
        marginBottom: 10,
    },
    description: {
        color: "#667085",
        fontSize: 15,
        lineHeight: 23,
        marginBottom: 25,
    },
    uploadCard: {
        backgroundColor: "#FFFFFF",
        borderRadius: 18,
        borderWidth: 1,
        borderColor: "#E4E7EC",
        padding: 15,
        marginBottom: 16,
    },
    preview: {
        width: "100%",
        height: 320,
        borderRadius: 12,
        backgroundColor: "#EAECF0",
        resizeMode: "contain",
        marginBottom: 15,
    },
    placeholder: {
        minHeight: 220,
        alignItems: "center",
        justifyContent: "center",
        padding: 22,
        marginBottom: 15,
        backgroundColor: "#F9FAFB",
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#EAECF0",
        borderStyle: "dashed",
    },
    placeholderIcon: {
        fontSize: 38,
        color: "#667085",
        marginBottom: 12,
    },
    placeholderTitle: {
        color: "#344054",
        fontSize: 16,
        fontWeight: "700",
        marginBottom: 6,
        textAlign: "center",
    },
    placeholderDescription: {
        color: "#667085",
        fontSize: 13,
        lineHeight: 20,
        textAlign: "center",
    },
    secondaryButton: {
        minHeight: 48,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 11,
        borderWidth: 1,
        borderColor: "#D0D5DD",
        paddingHorizontal: 14,
    },
    secondaryButtonText: {
        color: "#344054",
        fontSize: 14,
        fontWeight: "700",
    },
    fileName: {
        color: "#667085",
        fontSize: 12,
        marginTop: 10,
    },
    primaryButton: {
        minHeight: 54,
        borderRadius: 12,
        backgroundColor: "#157347",
        alignItems: "center",
        justifyContent: "center",
        padding: 14,
        marginBottom: 22,
    },
    primaryButtonText: {
        color: "#FFFFFF",
        fontSize: 15,
        fontWeight: "800",
    },
    loadingRow: {
        flexDirection: "row",
        alignItems: "center",
        gap: 10,
    },
    disabled: {
        opacity: 0.45,
    },
    pressed: {
        opacity: 0.8,
    },
    notice: {
        backgroundColor: "#FFF8E7",
        borderColor: "#F0D58A",
        borderWidth: 1,
        borderRadius: 12,
        padding: 15,
    },
    noticeTitle: {
        color: "#805B10",
        fontSize: 14,
        fontWeight: "800",
        marginBottom: 7,
    },
    noticeText: {
        color: "#715B2A",
        fontSize: 13,
        lineHeight: 20,
    },
});
