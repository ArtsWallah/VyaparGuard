
import { useCallback, useEffect, useState } from "react";
import {
    ActivityIndicator,
    Alert,
    Image,
    Pressable,
    ScrollView,
    StyleSheet,
    Text,
    View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as ImagePicker from "expo-image-picker";
import * as FileSystem from "expo-file-system/legacy";
import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { clearCapturedImage, getCapturedImage } from "@/services/image_cache";

const API_URL = "http://172.22.63.92:8000";

type SelectedImage = {
    uri: string;
    fileName?: string | null;
    mimeType?: string | null;
};

async function resolveValidUri(uri: string): Promise<string> {
    try {
        const info = await FileSystem.getInfoAsync(uri);
        if (info.exists) return uri;

        // In Expo Go on Android, ExperienceData directory contains '%2540' and '%252F'.
        // Expo Router's search params parser automatically decodes '%2540' -> '%40' and '%252F' -> '%2F'.
        // If decoded, reconstruct the original path.
        if (uri.includes("%40") || uri.includes("%2F")) {
            const restored = uri
                .replace(/%40/g, "%2540")
                .replace(/%2F/g, "%252F");
            const restoredInfo = await FileSystem.getInfoAsync(restored);
            if (restoredInfo.exists) {
                return restored;
            }
        }
    } catch {
        // Fall back to original URI
    }
    return uri;
}

export default function UploadScreen() {
    const params = useLocalSearchParams<{
        cameraUri?: string | string[];
    }>();

    const cameraUri = Array.isArray(params.cameraUri)
        ? params.cameraUri[0]
        : params.cameraUri;

    const [image, setImage] = useState<SelectedImage | null>(null);
    const [loading, setLoading] = useState(false);
    const [previewError, setPreviewError] = useState(false);

    // Pick up newly captured images from the live camera without URL-param corruption
    useFocusEffect(
        useCallback(() => {
            const captured = getCapturedImage();
            if (captured?.uri) {
                setImage({
                    uri: captured.uri,
                    fileName: captured.fileName || "camera-capture.jpg",
                    mimeType: captured.mimeType || "image/jpeg",
                });
                setPreviewError(false);
                clearCapturedImage();
            }
        }, [])
    );

    useEffect(() => {
        if (!cameraUri) return;

        let isMounted = true;

        async function initCameraUri(uri: string) {
            const resolvedUri = await resolveValidUri(uri);
            if (isMounted) {
                setImage({
                    uri: resolvedUri,
                    fileName: "camera-capture.jpg",
                    mimeType: "image/jpeg",
                });
                setPreviewError(false);
            }
        }

        initCameraUri(cameraUri);

        return () => {
            isMounted = false;
        };
    }, [cameraUri]);

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
            });
            setPreviewError(false);
        } catch (error) {
            Alert.alert(
                "Image selection failed",
                error instanceof Error ? error.message : "Please try again."
            );
        }
    }

    async function analyzeScreenshot() {
        if (!image || loading) {
            if (!image) {
                Alert.alert("Select an image", "Capture or choose an image first.");
            }
            return;
        }

        setLoading(true);

        try {
            // Verify that the local image is available before uploading.
            const uploadUri = await resolveValidUri(image.uri);
            const info = await FileSystem.getInfoAsync(uploadUri);

            if (!info.exists) {
                throw new Error(
                    "The image file is no longer available. Capture the screen again."
                );
            }

            const extension = image.fileName?.split(".").pop()?.toLowerCase();

            const mimeType =
                image.mimeType ||
                (extension === "png" ? "image/png" : "image/jpeg");

            // Upload the file URI directly without calling File.bytes().
            const response = await FileSystem.uploadAsync(
                `${API_URL}/api/v1/scan`,
                uploadUri,
                {
                    httpMethod: "POST",
                    uploadType: FileSystem.FileSystemUploadType.MULTIPART,
                    fieldName: "image",
                    mimeType,
                    parameters: {},
                }
            );

            let data: any;

            try {
                data = JSON.parse(response.body);
            } catch {
                throw new Error(
                    `Invalid server response (HTTP ${response.status}).`
                );
            }

            if (response.status < 200 || response.status >= 300) {
                const detail =
                    typeof data.detail === "string"
                        ? data.detail
                        : Array.isArray(data.detail)
                            ? data.detail
                                .map(
                                    (item: { msg?: string }) =>
                                        item.msg || "Invalid request"
                                )
                                .join("\n")
                            : `Upload failed (HTTP ${response.status}).`;

                throw new Error(detail);
            }

            router.push({
                pathname: "/result",
                params: {
                    result: JSON.stringify(data),
                },
            });
        } catch (error) {
            Alert.alert(
                "Analysis failed",
                error instanceof Error
                    ? `${error.message}\n\nBackend: ${API_URL}`
                    : "Could not upload the image. Please try again."
            );
        } finally {
            setLoading(false);
        }
    }

    const isCaptured = Boolean(
        cameraUri || image?.fileName?.startsWith("camera-capture")
    );

    return (
        <SafeAreaView style={styles.safeArea}>
            <ScrollView contentContainerStyle={styles.container}>
                <Pressable
                    onPress={() => router.back()}
                    style={styles.backButton}
                >
                    <Text style={styles.backText}>‹ Back</Text>
                </Pressable>

                <Text style={styles.eyebrow}>VYAPARGUARD / SCANNER</Text>

                <Text style={styles.title}>
                    {isCaptured ? "Review captured screen" : "Analyze payment screenshot"}
                </Text>

                <Text style={styles.description}>
                    Review the image of the other phone's screen, then extract the
                    visible transaction details.
                </Text>

                <View style={styles.uploadCard}>
                    {image && !previewError ? (
                        <Image
                            source={{ uri: image.uri }}
                            style={styles.preview}
                            resizeMode="contain"
                            onError={() => setPreviewError(true)}
                        />
                    ) : (
                        <View style={styles.placeholder}>
                            <Text style={styles.placeholderIcon}>
                                {previewError ? "!" : "▧"}
                            </Text>
                            <Text style={styles.placeholderTitle}>
                                {previewError ? "Preview unavailable" : "No image selected"}
                            </Text>
                            <Text style={styles.placeholderDescription}>
                                {previewError
                                    ? "The image could not be displayed. Capture or select it again."
                                    : "Capture a screen or choose a PNG/JPEG image."}
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
                            {image ? "Choose another image" : "Choose from gallery"}
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
                            Extract text and analyze →
                        </Text>
                    )}
                </Pressable>

                <Pressable
                    onPress={() => router.push("/camera")}
                    disabled={loading}
                    style={styles.cameraButton}
                >
                    <Text style={styles.cameraButtonText}>Open live camera</Text>
                </Pressable>

                <View style={styles.notice}>
                    <Text style={styles.noticeTitle}>Important verification notice</Text>
                    <Text style={styles.noticeText}>
                        The scanner extracts visible text and checks for possible image
                        manipulation indicators. This does not prove that money was
                        received. Confirm payment using trusted transaction records.
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
        marginBottom: 12,
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
    cameraButton: {
        minHeight: 48,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#157347",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: 22,
    },
    cameraButtonText: {
        color: "#157347",
        fontSize: 14,
        fontWeight: "800",
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
