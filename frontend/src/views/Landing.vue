<template>
  <div class="landing-page">
    <!-- Nav Bar -->
    <nav class="navbar">
      <div class="nav-container">
        <div class="nav-left" @click="router.push('/')">
          <span class="wordmark">Finally The Light</span>
        </div>
        <div class="nav-right">
          <button class="btn btn-filled" @click="router.push('/dashboard')">Mở Bảng điều khiển</button>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <div class="landing-container" style="padding-top: 96px;">
      <!-- Hero Section -->
      <section class="hero-section">
        <h1 class="hero-title">Dịch truyện, giữ trọn văn phong.</h1>
        <p class="hero-subtitle">
          Công cụ dịch thuật chuyên nghiệp tối ưu hóa bằng mô hình ngôn ngữ lớn.
          Tự động phân tách bối cảnh, trích xuất thuật ngữ và hiệu đính văn học.
        </p>
        <div class="hero-cta">
          <button class="btn btn-filled btn-lg" @click="router.push('/dashboard')">Bắt đầu dịch</button>
        </div>
      </section>

      <!-- Features Grid -->
      <section class="features-section">
        <div class="features-grid">
          <div class="feature-card">
            <svg class="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="7" height="7" rx="1"/>
              <rect x="14" y="3" width="7" height="7" rx="1"/>
              <rect x="3" y="14" width="7" height="7" rx="1"/>
              <rect x="14" y="14" width="7" height="7" rx="1"/>
            </svg>
            <h3 class="feature-title">Semantic Chunking</h3>
            <p class="feature-desc">
              Phân đoạn văn bản thông minh dựa trên ngữ nghĩa, đảm bảo mỗi phần dịch giữ trọn bối cảnh và mạch truyện.
              Không cắt đứt giữa đoạn hội thoại hay cảnh quan trọng.
            </p>
          </div>

          <div class="feature-card">
            <svg class="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 19.5v-15A2.5 2.5 0 016.5 2H20v20H6.5a2.5 2.5 0 010-5H20"/>
              <line x1="9" y1="7" x2="15" y2="7"/>
              <line x1="9" y1="11" x2="13" y2="11"/>
            </svg>
            <h3 class="feature-title">Trích xuất Glossary</h3>
            <p class="feature-desc">
              Tự động nhận diện và trích xuất thuật ngữ, tên riêng, danh xưng nhân vật.
              Duy trì bảng glossary nhất quán xuyên suốt toàn bộ tác phẩm.
            </p>
          </div>

          <div class="feature-card">
            <svg class="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 20h9"/>
              <path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
            </svg>
            <h3 class="feature-title">Biên tập & Hiệu đính</h3>
            <p class="feature-desc">
              Bước hiệu đính văn học tự động: chuẩn hóa văn phong, sửa lỗi ngữ pháp,
              và tinh chỉnh giọng văn cho phù hợp với thể loại tiểu thuyết.
            </p>
          </div>
        </div>
      </section>

      <!-- Footer -->
      <footer class="landing-footer">
        <p class="footer-content">© 2026 Finally The Light</p>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
.landing-page {
  min-height: 100vh;
  background-color: var(--color-bone);
}
</style>
