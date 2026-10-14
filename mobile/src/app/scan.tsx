
import React from "react";
import {
    SafeAreaView,
    View,
    Text,
    Pressable,
    StyleSheet,
} from "react-native";
import { useRouter } from "expo-router";

export default function ScanScreen() {
    const router = useRouter();

    return (
        <SafeAreaView style={styles.container}>
            <Pressable onPress={() => router.back()} style={styles.backButton}>
                <Text style={styles.backText}>‹  Back</Text>
            </Pressable>

            <View style={styles.content}>
                <View style={styles.iconBox}>
                    <Text style={styles.icon}>↥</Text>
                </View>

                <Text style={styles.title}>Analyze a payment</Text>
                <Text style={styles.description}>
                    Choose a payment screenshot to inspect its details and check
                    whether a trusted transaction record is available.
                </Text>

                <Pressable
                    style={styles.button}
                    onPress={() => router.push("/upload")}
                >
                    <Text style={styles.buttonText}>Choose Screenshot</Text>
                </Pressable>

                <Text style={styles.note}>
                    A screenshot alone is not proof of a completed payment.
                </Text>
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: "#F8FAFC",
        padding: 22,
    },
    backButton: {
        alignSelf: "flex-start",
        paddingVertical: 8,
    },
    backText: {
        color: "#176B55",
        fontSize: 17,
        fontWeight: "600",
    },
    content: {
        flex: 1,
        justifyContent: "center",
        alignItems: "center",
    },
    iconBox: {
        height: 90,
        width: 90,
        borderRadius: 25,
        backgroundColor: "#E4F3ED",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: 24,
    },
    icon: {
        fontSize: 48,
        color: "#176B55",
    },
    title: {
        fontSize: 26,
        fontWeight: "800",
        color: "#102A43",
        textAlign: "center",
    },
    description: {
        fontSize: 14,
        lineHeight: 22,
        color: "#64748B",
        textAlign: "center",
        marginTop: 12,
        marginBottom: 28,
    },
    button: {
        backgroundColor: "#176B55",
        padding: 17,
        borderRadius: 14,
        width: "100%",
        alignItems: "center",
    },
    buttonText: {
        color: "#FFFFFF",
        fontSize: 15,
        fontWeight: "700",
    },
    note: {
        marginTop: 18,
        color: "#64748B",
        textAlign: "center",
        fontSize: 12,
        lineHeight: 19,
    },
});
