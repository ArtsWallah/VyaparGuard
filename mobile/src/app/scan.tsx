
import React from 'react';
import {
  Pressable,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";

export default function ScanScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar
        barStyle="dark-content"
        backgroundColor="#F8FAFC"
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        <Pressable
          accessibilityRole="button"
          onPress={() => router.back()}
          style={styles.backButton}
        >
          <Text style={styles.backText}>‹  Back</Text>
        </Pressable>

        <View style={styles.content}>
          <View style={styles.iconBox}>
            <Text style={styles.icon}>↑</Text>
          </View>

          <Text style={styles.eyebrow}>PAYMENT SCREENING</Text>

          <Text style={styles.title}>
            Check before you accept.
          </Text>

          <Text style={styles.description}>
            Select the payment screenshot you received. VyaparGuard
            will display the result returned by the connected
            analysis service.
          </Text>

          <View style={styles.infoCard}>
            <View style={styles.infoRow}>
              <View style={styles.numberCircle}>
                <Text style={styles.numberText}>1</Text>
              </View>
              <View style={styles.infoContent}>
                <Text style={styles.infoTitle}>
                  Choose an image
                </Text>
                <Text style={styles.infoDescription}>
                  Select a payment screenshot from your gallery.
                </Text>
              </View>
            </View>

            <View style={styles.infoDivider} />

            <View style={styles.infoRow}>
              <View style={styles.numberCircle}>
                <Text style={styles.numberText}>2</Text>
              </View>
              <View style={styles.infoContent}>
                <Text style={styles.infoTitle}>
                  Review the result
                </Text>
                <Text style={styles.infoDescription}>
                  Check the status, available details and warnings.
                </Text>
              </View>
            </View>
          </View>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Choose payment screenshot"
            style={({ pressed }) => [
              styles.button,
              pressed && styles.buttonPressed,
            ]}
            onPress={() => router.push('/upload')}
          >
            <Text style={styles.buttonText}>
              Choose Payment Screenshot
            </Text>
            <Text style={styles.buttonArrow}>→</Text>
          </Pressable>

          <Text style={styles.helperText}>
            Choose a clear screenshot in JPG, PNG or WebP format.
          </Text>

          <View style={styles.warningCard}>
            <Text style={styles.warningTitle}>
              Important safety reminder
            </Text>
            <Text style={styles.warningText}>
              A screenshot cannot prove that money reached your
              account. Confirm the payment in your own bank or
              UPI transaction history before handing over goods.
            </Text>
          </View>

          <Text style={styles.footer}>
            VyaparGuard · Safer payment decisions
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollContent: {
    flexGrow: 1,
    padding: 22,
    paddingBottom: 35,
  },
  backButton: {
    alignSelf: 'flex-start',
    paddingVertical: 8,
    paddingRight: 15,
  },
  backText: {
    color: '#176B55',
    fontSize: 16,
    fontWeight: '700',
  },
  content: {
    flexGrow: 1,
    alignItems: 'center',
    paddingTop: 24,
  },
  iconBox: {
    height: 78,
    width: 78,
    borderRadius: 24,
    backgroundColor: '#E4F3ED',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  icon: {
    fontSize: 43,
    fontWeight: '700',
    color: '#176B55',
  },
  eyebrow: {
    color: '#176B55',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.5,
    marginBottom: 10,
  },
  title: {
    fontSize: 27,
    lineHeight: 34,
    fontWeight: '800',
    color: '#102A43',
    textAlign: 'center',
  },
  description: {
    fontSize: 14,
    lineHeight: 22,
    color: '#64748B',
    textAlign: 'center',
    marginTop: 12,
    marginBottom: 25,
  },
  infoCard: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 17,
    borderWidth: 1,
    borderColor: '#E8EEF2',
    paddingHorizontal: 16,
    paddingVertical: 17,
    marginBottom: 22,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  numberCircle: {
    height: 34,
    width: 34,
    borderRadius: 12,
    backgroundColor: '#E4F3ED',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  numberText: {
    color: '#176B55',
    fontSize: 14,
    fontWeight: '800',
  },
  infoContent: {
    flex: 1,
  },
  infoTitle: {
    color: '#102A43',
    fontSize: 14,
    fontWeight: '700',
  },
  infoDescription: {
    color: '#64748B',
    fontSize: 12,
    lineHeight: 18,
    marginTop: 4,
  },
  infoDivider: {
    height: 1,
    backgroundColor: '#E8EEF2',
    marginVertical: 15,
  },
  button: {
    backgroundColor: '#176B55',
    paddingHorizontal: 15,
    paddingVertical: 17,
    borderRadius: 14,
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
    textAlign: 'center',
    flexShrink: 1,
  },
  buttonArrow: {
    color: '#FFFFFF',
    fontSize: 21,
    marginLeft: 9,
  },
  buttonPressed: {
    opacity: 0.82,
  },
  helperText: {
    marginTop: 10,
    marginBottom: 22,
    color: '#64748B',
    textAlign: 'center',
    fontSize: 11,
    lineHeight: 17,
  },
  warningCard: {
    width: '100%',
    backgroundColor: '#FFF5DE',
    borderRadius: 15,
    padding: 16,
  },
  warningTitle: {
    color: '#8A5A00',
    fontSize: 14,
    fontWeight: '800',
    marginBottom: 7,
  },
  warningText: {
    color: '#725B32',
    fontSize: 12,
    lineHeight: 20,
  },
  footer: {
    textAlign: 'center',
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 24,
  },
});
