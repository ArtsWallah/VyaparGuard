import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  Pressable,
  Image,
  Alert,
  ActivityIndicator,
  StatusBar,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system/legacy';
import { isScanResult } from '../utils/scan-result';
import { getCapturedImage, clearCapturedImage } from '@/services/image_cache';

type SelectedImage = Pick<ImagePicker.ImagePickerAsset, 'uri'> & {
  fileName?: string | null;
  mimeType?: string | null;
  fileSize?: number | null;
  webFile?: File;
};

const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://127.0.0.1:8000';
// Local development only; use HTTPS in production.

export default function UploadScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    cameraUri?: string | string[];
  }>();

  const cameraUri = Array.isArray(params.cameraUri)
    ? params.cameraUri[0]
    : params.cameraUri;

  const [image, setImage] = useState<SelectedImage | null>(null);
  const [loading, setLoading] = useState(false);
  const webInputRef = useRef<HTMLInputElement>(null);

  // Pick up newly captured images from the live camera without URL-param corruption
  useFocusEffect(
    useCallback(() => {
      const captured = getCapturedImage();
      if (captured?.uri) {
        setImage({
          uri: captured.uri,
          fileName: captured.fileName || 'camera-capture.jpg',
          mimeType: captured.mimeType || 'image/jpeg',
          fileSize: captured.fileSize ?? null,
        });
        clearCapturedImage();
      }
    }, [])
  );

  useEffect(() => {
    if (!cameraUri) return;
    setImage({
      uri: cameraUri,
      fileName: 'camera-capture.jpg',
      mimeType: 'image/jpeg',
    });
  }, [cameraUri]);

  useEffect(() => {
    if (!image?.webFile) return;

    const imageUri = image.uri;
    return () => URL.revokeObjectURL(imageUri);
  }, [image]);

  function handleWebImageChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';

    if (!file) return;

    setImage({
      uri: URL.createObjectURL(file),
      fileName: file.name,
      mimeType: file.type || null,
      fileSize: file.size,
      webFile: file,
    });
  }

  async function chooseImage() {
    if (loading) return;

    if (Platform.OS === 'web') {
      webInputRef.current?.click();
      return;
    }

    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert(
          'Permission required',
          'Allow photo library access to select a payment screenshot.'
        );
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: false,
        quality: 1,
      });

      if (!result.canceled && result.assets.length > 0) {
        setImage(result.assets[0]);
      }
    } catch {
      Alert.alert(
        'Unable to open gallery',
        'Please try again or select your screenshot from the gallery.'
      );
    }
  }

  async function analyzeImage() {
    if (!image) {
      Alert.alert(
        'Select a screenshot',
        'Choose a payment screenshot before starting the analysis.'
      );
      return;
    }

    if (image.fileSize && image.fileSize > 10 * 1024 * 1024) {
      Alert.alert(
        'File too large',
        'The selected image exceeds the 10 MB processing limit. Please choose a smaller image.'
      );
      return;
    }

    if (loading) return;

    setLoading(true);

    try {
      const extension = image.fileName?.split('.').pop()?.toLowerCase();
      const mimeType =
        image.mimeType || (extension === 'png' ? 'image/png' : 'image/jpeg');
      const fileName =
        image.fileName || `payment-screenshot.${extension || 'jpg'}`;

      let responseStatus: number;
      let responseText: string;

      if (Platform.OS !== 'web' && !image.webFile) {
        try {
          const uploadResult = await FileSystem.uploadAsync(
            `${API_URL}/api/v1/scan`,
            image.uri,
            {
              httpMethod: 'POST',
              uploadType: FileSystem.FileSystemUploadType.MULTIPART,
              fieldName: 'image',
              mimeType,
            }
          );
          responseStatus = uploadResult.status;
          responseText = uploadResult.body;
        } catch {
          const formData = new FormData();
          formData.append(
            'image',
            {
              uri: image.uri,
              name: fileName,
              type: mimeType,
            } as unknown as Blob
          );

          const response = await fetch(`${API_URL}/api/v1/scan`, {
            method: 'POST',
            body: formData,
          });
          responseStatus = response.status;
          responseText = await response.text();
        }
      } else {
        const formData = new FormData();
        if (image.webFile) {
          formData.append('image', image.webFile, fileName);
        } else {
          const imageResponse = await fetch(image.uri);
          if (!imageResponse.ok) {
            throw new Error('Unable to read the selected screenshot.');
          }
          const blob = await imageResponse.blob();
          formData.append('image', blob, fileName);
        }

        const response = await fetch(`${API_URL}/api/v1/scan`, {
          method: 'POST',
          body: formData,
        });
        responseStatus = response.status;
        responseText = await response.text();
      }

      let data: unknown;

      try {
        data = JSON.parse(responseText);
      } catch {
        throw new Error(
          `The server returned an invalid response (HTTP ${responseStatus}).`
        );
      }

      if (responseStatus < 200 || responseStatus >= 300) {
        const detail =
          typeof data === 'object' &&
          data !== null &&
          'detail' in data &&
          typeof (data as Record<string, unknown>).detail === 'string'
            ? String((data as Record<string, unknown>).detail)
            : 'The server could not process this image.';

        throw new Error(
          typeof detail === 'string'
            ? detail
            : `The server could not process this image (HTTP ${responseStatus}).`
        );
      }

      if (!isScanResult(data)) {
        throw new Error(
          'The server returned an unexpected result. Please try again.'
        );
      }

      router.push({
        pathname: '/result',
        params: {
          result: JSON.stringify(data),
        },
      });
    } catch (error) {
      Alert.alert(
        'Unable to analyze screenshot',
        error instanceof Error
          ? `${error.message}\n\nCheck that the backend is running and the API address is correct. Your phone and laptop must be able to communicate over the network.`
          : 'An unexpected error occurred. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar
        barStyle="dark-content"
        backgroundColor="#F8FAFC"
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        <Pressable
          accessibilityRole="button"
          onPress={() => router.back()}
          disabled={loading}
          style={styles.backButton}
        >
          <Text style={styles.backText}>‹  Back</Text>
        </Pressable>

        <Text style={styles.eyebrow}>PAYMENT SCREENING</Text>

        <Text style={styles.title}>Upload Payment</Text>

        <Text style={styles.description}>
          Select the screenshot you received or open the camera to begin the
          available checks.
        </Text>

        <View style={styles.uploadCard}>
          {Platform.OS === 'web' && (
            <input
              ref={webInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleWebImageChange}
              disabled={loading}
              aria-label="Select a payment screenshot"
              style={{ display: 'none' }}
            />
          )}

          <View style={styles.uploadIcon}>
            <Text style={styles.uploadIconText}>↑</Text>
          </View>

          <Text style={styles.uploadTitle}>
            {image ? 'Screenshot selected' : 'Choose a screenshot'}
          </Text>

          <Text style={styles.uploadDescription}>
            Select an image from your gallery or open the camera to preview it before
            sending it for analysis.
          </Text>

          <Pressable
            accessibilityRole="button"
            onPress={chooseImage}
            disabled={loading}
            style={({ pressed }) => [
              styles.chooseButton,
              pressed && styles.buttonPressed,
              loading && styles.disabled,
            ]}
          >
            <Text style={styles.chooseText}>
              {image ? 'Choose Another Image' : 'Select from Gallery'}
            </Text>
          </Pressable>

          <Text style={styles.formatText}>
            Supported formats: JPG, PNG and WebP · Maximum 10 MB
          </Text>
        </View>

        {image && (
          <View style={styles.previewContainer}>
            <View style={styles.previewHeader}>
              <Text style={styles.previewTitle}>Image preview</Text>
              <Pressable
                onPress={() => setImage(null)}
                disabled={loading}
              >
                <Text style={styles.removeText}>Remove</Text>
              </Pressable>
            </View>

            <Image
              source={{ uri: image.uri }}
              style={styles.preview}
              accessibilityLabel="Selected payment screenshot preview"
            />

            <Text style={styles.fileName} numberOfLines={2}>
              {image.fileName || 'Selected screenshot'}
            </Text>

            {image.fileSize != null && (
              <Text style={styles.fileSize}>
                {(image.fileSize / (1024 * 1024)).toFixed(2)} MB
              </Text>
            )}
          </View>
        )}

        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Analyze screenshot"
          style={({ pressed }) => [
            styles.analyzeButton,
            (!image || loading) && styles.disabled,
            pressed && !loading && styles.buttonPressed,
          ]}
          onPress={analyzeImage}
          disabled={!image || loading}
        >
          {loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color="#FFFFFF" size="small" />
              <Text style={styles.analyzeText}>
                Sending for analysis...
              </Text>
            </View>
          ) : (
            <Text style={styles.analyzeText}>
              Analyze Screenshot  →
            </Text>
          )}
        </Pressable>

        <Pressable
          accessibilityRole="button"
          onPress={() => router.push("/camera")}
          disabled={loading}
          style={({ pressed }) => [
            styles.cameraButton,
            pressed && styles.buttonPressed,
            loading && styles.disabled,
          ]}
        >
          <Text style={styles.cameraButtonText}>Open Live Camera</Text>
        </Pressable>

        <View style={styles.notice}>
          <Text style={styles.noticeTitle}>
            Important safety reminder
          </Text>
          <Text style={styles.noticeText}>
            A screenshot alone cannot prove that a payment was
            completed. Confirm the transaction in your own bank
            or UPI history before accepting payment.
          </Text>
        </View>

        <View style={styles.demoNotice}>
          <Text style={styles.demoTitle}>Demo mode</Text>
          <Text style={styles.demoText}>
            The current backend returns UNVERIFIED while full
            screenshot analysis and trusted transaction matching
            are not implemented. A result does not confirm that
            money was received.
          </Text>
        </View>

        <Text style={styles.footer}>
          VyaparGuard · Safer payment decisions
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  content: {
    padding: 22,
    paddingBottom: 110,
  },
  backButton: {
    alignSelf: 'flex-start',
    paddingVertical: 8,
    marginBottom: 19,
  },
  backText: {
    color: '#176B55',
    fontSize: 16,
    fontWeight: '700',
  },
  eyebrow: {
    color: '#176B55',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.5,
    marginBottom: 8,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#102A43',
  },
  description: {
    fontSize: 14,
    lineHeight: 22,
    color: '#64748B',
    marginTop: 9,
    marginBottom: 23,
  },
  uploadCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 21,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#DCEAE4',
    borderStyle: 'dashed',
  },
  uploadIcon: {
    width: 58,
    height: 58,
    borderRadius: 18,
    backgroundColor: '#E4F3ED',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 15,
  },
  uploadIconText: {
    fontSize: 34,
    color: '#176B55',
    fontWeight: '700',
  },
  uploadTitle: {
    color: '#102A43',
    fontSize: 17,
    fontWeight: '800',
    textAlign: 'center',
  },
  uploadDescription: {
    color: '#64748B',
    fontSize: 12,
    lineHeight: 19,
    textAlign: 'center',
    marginTop: 8,
    marginBottom: 18,
  },
  chooseButton: {
    paddingHorizontal: 21,
    paddingVertical: 13,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#176B55',
    alignItems: 'center',
  },
  chooseText: {
    color: '#176B55',
    fontSize: 13,
    fontWeight: '700',
  },
  formatText: {
    color: '#94A3B8',
    fontSize: 10,
    textAlign: 'center',
    marginTop: 14,
    lineHeight: 16,
  },
  previewContainer: {
    marginTop: 20,
    backgroundColor: '#FFFFFF',
    borderRadius: 17,
    padding: 13,
    borderWidth: 1,
    borderColor: '#E8EEF2',
  },
  previewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  previewTitle: {
    color: '#102A43',
    fontSize: 14,
    fontWeight: '800',
  },
  removeText: {
    color: '#B42318',
    fontSize: 12,
    fontWeight: '700',
    padding: 4,
  },
  preview: {
    width: '100%',
    height: 300,
    resizeMode: 'contain',
    backgroundColor: '#F8FAFC',
    borderRadius: 10,
  },
  fileName: {
    color: '#64748B',
    fontSize: 12,
    marginTop: 11,
  },
  fileSize: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 4,
  },
  analyzeButton: {
    backgroundColor: '#176B55',
    padding: 18,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 22,
    minHeight: 55,
  },
  analyzeText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  cameraButton: {
    minHeight: 50,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#176B55',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
  },
  cameraButtonText: {
    color: '#176B55',
    fontSize: 14,
    fontWeight: '700',
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  disabled: {
    opacity: 0.55,
  },
  buttonPressed: {
    opacity: 0.82,
  },
  notice: {
    backgroundColor: '#FFF5DE',
    borderRadius: 15,
    padding: 16,
    marginTop: 20,
  },
  noticeTitle: {
    color: '#8A5A00',
    fontSize: 13,
    fontWeight: '800',
    marginBottom: 6,
  },
  noticeText: {
    color: '#725B32',
    fontSize: 12,
    lineHeight: 19,
  },
  demoNotice: {
    backgroundColor: '#F1F5F9',
    borderRadius: 15,
    padding: 16,
    marginTop: 12,
  },
  demoTitle: {
    color: '#334155',
    fontSize: 13,
    fontWeight: '800',
    marginBottom: 6,
  },
  demoText: {
    color: '#64748B',
    fontSize: 12,
    lineHeight: 19,
  },
  footer: {
    textAlign: 'center',
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 24,
  },
});