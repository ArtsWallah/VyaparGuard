
import React from "react";
import {
  ScrollView,
  View,
  Text,
  Pressable,
  StyleSheet,
  StatusBar,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";

export default function HomeScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" backgroundColor="#F8FAFC" />

      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View>
            <Text style={styles.brand}>VyaparGuard</Text>
            <Text style={styles.subtitle}>
              Smarter payment screenshot checks
            </Text>
          </View>

          <View style={styles.logo}>
            <Text style={styles.logoText}>V</Text>
          </View>
        </View>

        <View style={styles.hero}>
          <View style={styles.shield}>
            <Text style={styles.shieldText}>✓</Text>
          </View>

          <Text style={styles.heroTitle}>Verify before you trust.</Text>
          <Text style={styles.heroDescription}>
            Inspect payment screenshots for suspicious signs and compare
            their details with trusted transaction records.
          </Text>
        </View>

        <Pressable
          style={styles.primaryButton}
          onPress={() => router.push("/upload")}
        >
          <Text style={styles.primaryButtonText}>
            +  Analyze Payment Screenshot
          </Text>
        </Pressable>

        <View style={styles.notice}>
          <Text style={styles.noticeTitle}>Stay protected</Text>
          <Text style={styles.noticeText}>
            A screenshot alone cannot confirm that money was received.
            Always check your actual transaction history.
          </Text>
        </View>

        <Text style={styles.sectionTitle}>How it works</Text>

        {[
          {
            number: "01",
            title: "Extract payment details",
            description: "Read the amount, date and reference ID.",
          },
          {
            number: "02",
            title: "Inspect the screenshot",
            description: "Check for duplicates and possible editing indicators.",
          },
          {
            number: "03",
            title: "Check trusted records",
            description: "Compare payment details before assigning a result.",
          },
        ].map((item) => (
          <View style={styles.stepCard} key={item.number}>
            <Text style={styles.stepNumber}>{item.number}</Text>
            <View style={styles.stepContent}>
              <Text style={styles.stepTitle}>{item.title}</Text>
              <Text style={styles.stepDescription}>
                {item.description}
              </Text>
            </View>
          </View>
        ))}

        <Text style={styles.footer}>
          VyaparGuard · Payment verification assistance
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
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 30,
  },
  brand: {
    fontSize: 25,
    fontWeight: "800",
    color: "#102A43",
  },
  subtitle: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 5,
  },
  logo: {
    width: 48,
    height: 48,
    borderRadius: 15,
    backgroundColor: "#176B55",
    alignItems: "center",
    justifyContent: "center",
  },
  logoText: {
    color: "#FFFFFF",
    fontSize: 25,
    fontWeight: "800",
  },
  hero: {
    backgroundColor: "#E4F3ED",
    borderRadius: 24,
    padding: 24,
    marginBottom: 20,
  },
  shield: {
    width: 58,
    height: 58,
    borderRadius: 18,
    backgroundColor: "#176B55",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },
  shieldText: {
    fontSize: 34,
    color: "#FFFFFF",
    fontWeight: "800",
  },
  heroTitle: {
    fontSize: 28,
    lineHeight: 35,
    fontWeight: "800",
    color: "#102A43",
  },
  heroDescription: {
    color: "#46645A",
    fontSize: 14,
    lineHeight: 22,
    marginTop: 12,
  },
  primaryButton: {
    backgroundColor: "#176B55",
    borderRadius: 15,
    padding: 18,
    alignItems: "center",
    marginBottom: 20,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },
  notice: {
    backgroundColor: "#FFF5DE",
    borderRadius: 15,
    padding: 17,
    marginBottom: 30,
  },
  noticeTitle: {
    color: "#8A5A00",
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 6,
  },
  noticeText: {
    color: "#725B32",
    fontSize: 13,
    lineHeight: 20,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: "#102A43",
    marginBottom: 14,
  },
  stepCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: "#FFFFFF",
    borderRadius: 15,
    padding: 16,
    marginBottom: 11,
    borderWidth: 1,
    borderColor: "#E8EEF2",
  },
  stepNumber: {
    color: "#176B55",
    fontSize: 17,
    fontWeight: "800",
    marginRight: 15,
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    color: "#102A43",
    fontSize: 14,
    fontWeight: "700",
  },
  stepDescription: {
    color: "#64748B",
    fontSize: 12,
    lineHeight: 19,
    marginTop: 5,
  },
  footer: {
    textAlign: "center",
    color: "#94A3B8",
    fontSize: 11,
    marginTop: 25,
  },
});
