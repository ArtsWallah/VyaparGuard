
import { useRef, useState } from "react";
import {
    ActivityIndicator,
    Alert,
    Pressable,
    StyleSheet,
    Text,
    View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
    CameraView,
    useCameraPermissions,
} from "expo-camera";
import * as FileSystem from "expo-file-system/legacy";
import { router } from "expo-router";
import { setCapturedImage } from "@/services/image_cache";

export default function CameraScreen() {
    const cameraRef = useRef<CameraView>(null);
    const [permission, requestPermission] = useCameraPermissions();
    const [capturing, setCapturing] = useState(false);

    async function captureScreen() {
        if (!cameraRef.current || capturing) return;

        setCapturing(true);

        try {
            const photo = await cameraRef.current.takePictureAsync({
                quality: 0.85,
                skipProcessing: false,
            });

            if (!photo?.uri) {
                throw new Error("The camera did not return an image.");
            }

            // Confirm the original capture exists.
            const original = await FileSystem.getInfoAsync(photo.uri);

            if (!original.exists) {
                throw new Error("The captured image was not saved.");
            }

            // Try copying the image to a persistent cache path if available
            let targetUri = photo.uri;
            try {
                const cacheDirectory = FileSystem.cacheDirectory;
                if (cacheDirectory) {
                    const stableUri = `${cacheDirectory}vyaparguard-${Date.now()}.jpg`;
                    await FileSystem.copyAsync({
                        from: photo.uri,
                        to: stableUri,
                    });

                    const copied = await FileSystem.getInfoAsync(stableUri);
                    if (copied.exists) {
                        targetUri = stableUri;
                    }
                }
            } catch (copyErr) {
                console.warn("Could not copy photo to cacheDirectory, using photo.uri:", copyErr);
            }

            // Store in shared in-memory image cache so that the URI never gets corrupted by URL encoding in router params
            setCapturedImage({
                uri: targetUri,
                fileName: "camera-capture.jpg",
                mimeType: "image/jpeg",
            });

            if (router.canGoBack()) {
                router.back();
            } else {
                router.replace({
                    pathname: "/upload",
                    params: {
                        cameraUri: targetUri,
                    },
                });
            }
        } catch (error) {
            Alert.alert(
                "Capture failed",
                error instanceof Error
                    ? error.message
                    : "Could not capture the payment screen."
            );
        } finally {
            setCapturing(false);
        }
    }

    if (!permission) {
        return (
            <SafeAreaView style={styles.center}>
                <ActivityIndicator size="large" />
                <Text style={styles.message}>Checking camera permission...</Text>
            </SafeAreaView>
        );
    }

    if (!permission.granted) {
        return (
            <SafeAreaView style={styles.center}>
                <Text style={styles.title}>Camera permission needed</Text>
                <Text style={styles.message}>
                    Allow camera access to scan the payment screen on another phone.
                </Text>
                <Pressable
                    style={styles.button}
                    onPress={requestPermission}
                >
                    <Text style={styles.buttonText}>Allow camera access</Text>
                </Pressable>
            </SafeAreaView>
        );
    }

    return (
        <SafeAreaView style={styles.screen}>
            <View style={styles.header}>
                <Pressable onPress={() => router.back()}>
                    <Text style={styles.back}>‹ Back</Text>
                </Pressable>
                <Text style={styles.headerTitle}>Live payment scanner</Text>
            </View>

            <View style={styles.cameraWrapper}>
                <CameraView
                    ref={cameraRef}
                    style={StyleSheet.absoluteFill}
                    facing="back"
                    mode="picture"
                />
                <View style={styles.overlay} pointerEvents="box-none">
                    <View style={styles.scanFrame} />
                    <Text style={styles.hint}>
                        Align the other phone's payment screen inside the frame.
                    </Text>
                </View>
            </View>

            <View style={styles.controls}>
                <Text style={styles.instructions}>
                    Keep both phones steady and make sure the amount, payee, and
                    transaction reference are clearly visible.
                </Text>

                <Pressable
                    style={[styles.button, capturing && styles.disabled]}
                    onPress={captureScreen}
                    disabled={capturing}
                >
                    {capturing ? (
                        <ActivityIndicator color="#FFFFFF" />
                    ) : (
                        <Text style={styles.buttonText}>Capture payment screen</Text>
                    )}
                </Pressable>

                <Text style={styles.disclaimer}>
                    A captured screen is not proof that a payment was received.
                </Text>
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    screen: {
        flex: 1,
        backgroundColor: "#101828",
    },
    center: {
        flex: 1,
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#F7F8FA",
        padding: 24,
    },
    header: {
        minHeight: 58,
        paddingHorizontal: 18,
        flexDirection: "row",
        alignItems: "center",
        gap: 18,
        backgroundColor: "#FFFFFF",
    },
    back: {
        fontSize: 16,
        color: "#176B55",
        fontWeight: "700",
    },
    headerTitle: {
        fontSize: 17,
        color: "#101828",
        fontWeight: "800",
    },
    cameraWrapper: {
        flex: 1,
        position: "relative",
    },
    overlay: {
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
    },
    scanFrame: {
        width: "92%",
        height: "48%",
        borderWidth: 2,
        borderColor: "#4ADE80",
        borderRadius: 18,
    },
    hint: {
        color: "#FFFFFF",
        fontSize: 14,
        fontWeight: "700",
        textAlign: "center",
        marginTop: 24,
        backgroundColor: "#101828CC",
        padding: 10,
        borderRadius: 8,
        overflow: "hidden",
    },
    controls: {
        padding: 20,
        backgroundColor: "#FFFFFF",
        gap: 14,
    },
    title: {
        fontSize: 22,
        fontWeight: "800",
        color: "#101828",
        marginBottom: 10,
    },
    message: {
        color: "#667085",
        fontSize: 14,
        textAlign: "center",
        lineHeight: 21,
        marginTop: 10,
        marginBottom: 16,
    },
    instructions: {
        fontSize: 13,
        lineHeight: 20,
        color: "#475467",
    },
    button: {
        minHeight: 52,
        paddingHorizontal: 16,
        borderRadius: 12,
        backgroundColor: "#176B55",
        justifyContent: "center",
        alignItems: "center",
    },
    buttonText: {
        color: "#FFFFFF",
        fontSize: 15,
        fontWeight: "800",
    },
    disabled: {
        opacity: 0.6,
    },
    disclaimer: {
        color: "#667085",
        fontSize: 11,
        lineHeight: 17,
        textAlign: "center",
    },
});
