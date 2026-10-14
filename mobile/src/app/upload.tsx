
import React, { useState } from "react";
import {
    SafeAreaView,
    ScrollView,
    View,
    Text,
    StyleSheet,
    Pressable,
    Image,
    Alert,
    ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";

type ScanResult = {
    scan_id: string;
    status: "VERIFIED" | "SUSPICIOUS" | "UNVERIFIED";
    extracted?: {
        amount?: number | null;
        transaction_id?: string | null;
        date?: string | null;
    };
    reasons?: string[];
    verification_source?: string;
};

const API_URL = "http://192.168.1.10:8000";
// Replace this with your laptop's actual IPv4 address.

export default function UploadScreen() {
    const router = useRouter();
    const [image, setImage] = useState<ImagePicker.ImagePickerAsset | null>(
        null
    );
    const [loading, setLoading] = useState(false);

    async function chooseImage() {
        try {
            const result = await ImagePicker.launchImageLibraryAsync({
                mediaTypes: ["images"],
                allowsEditing: false,
                quality: 1,
            });

            if (!result.canceled && result.assets.length > 0) {
                setImage(result.assets[0]);
            }
        } catch {
            Alert.alert("Image error", "Could not open the image gallery.");
        }
    }

    async function analyzeImage() {
        if (!image) {
            Alert.alert("Select an image", "Choose a screenshot first.");
            return;
        }

        setLoading(true);

        try {
            const formData = new FormData();

            formData.append(
                "image",
                {
                    uri: image.uri,
                    name: image.fileName || "payment-screenshot.jpg",
                    type: image.mimeType || "image/jpeg",
                } as unknown as Blob
            );

            const response = await fetch(`${API_URL}/api/v1/scan`, {
                method: "POST",
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "The backend rejected the image."
                );
            }

            const result = data as ScanResult;

            router.push({
                pathname: "/result",
                params: {
                    result: JSON.stringify(result),
                },
            });
        } catch (error) {
            Alert.alert(
                "Unable to analyze",
                error instanceof Error
                    ? `${error.message}\n\nCheck that the backend is running, your API address is correct, and your phone can reach your laptop.`
                    : "An unexpected error occurred."
            );
        } finally {
            setLoading(false);
        }
    }

    return (
        <SafeAreaView style={styles.container}>
            <ScrollView contentContainerStyle={styles.content}>
                <Pressable onPress={() => router.back()}>
                    <Text style={styles.backText}>‹  Back</Text>
                </Pressable>

                <Text style={styles.title}>Upload Payment</Text>
                <Text style={styles.description}>
                    Choose a screenshot for inspection.
                </Text>

                <Pressable style={styles.chooseButton} onPress={chooseImage}>
                    <Text style={styles.chooseText}>
                        {image ? "Choose Another Image" : "Choose Screenshot"}
                    </Text>
                </Pressable>

                {image && (
                    <View style={styles.previewContainer}>
                        <Image source={{ uri: image.uri }} style={styles.preview} />
                        <Text style={styles.fileName}>
                            {image.fileName || "Selected screenshot"}
                        </Text>
                    </View>
                )}

                <Pressable
                    style={[styles.analyzeButton, loading && styles.disabled]}
                    onPress={analyzeImage}
                    disabled={loading}
                >
                    {loading ? (
                        <ActivityIndicator color="#FFFFFF" />
                    ) : (
                        <Text style={styles.analyzeText}>Analyze Screenshot</Text>
                    )}
                </Pressable>

                <Text style={styles.note}>
                    The current backend is a placeholder. It returns UNVERIFIED until
                    OCR, image checks and trusted-record reconciliation are implemented.
                </Text>
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: "#F8FAFC",
    },
    content: {
        padding: 22,
        paddingBottom: 36,
    },
    backText: {
        color: "#176B55",
        fontSize: 17,
        fontWeight: "600",
        marginBottom: 20,
    },
    title: {
        fontSize: 27,
        fontWeight: "800",
        color: "#102A43",
    },
    description: {
        fontSize: 14,
        lineHeight: 22,
        color: "#64748B",
        marginTop: 10,
        marginBottom: 25,
    },
    chooseButton: {
        padding: 17,
        borderRadius: 14,
        borderWidth: 1,
        borderColor: "#176B55",
        alignItems: "center",
    },
    chooseText: {
        color: "#176B55",
        fontWeight: "700",
    },
    previewContainer: {
        marginTop: 20,
        backgroundColor: "#FFFFFF",
        borderRadius: 14,
        padding: 10,
    },
    preview: {
        width: "100%",
        height: 350,
        resizeMode: "contain",
    },
    fileName: {
        color: "#64748B",
        fontSize: 12,
        marginTop: 8,
    },
    analyzeButton: {
        backgroundColor: "#176B55",
        padding: 18,
        borderRadius: 14,
        alignItems: "center",
        marginTop: 22,
    },
    analyzeText: {
        color: "#FFFFFF",
        fontWeight: "700",
        fontSize: 15,
    },
    disabled: {
        opacity: 0.6,
    },
    note: {
        color: "#64748B",
        fontSize: 12,
        lineHeight: 19,
        marginTop: 18,
    },
});
