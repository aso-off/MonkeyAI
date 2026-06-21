<template>
  <div class="flex">
    <!-- Выпадающий список выбора модели -->
    <div
      class="gpt-model-select-wrapper"
      ref="modelDropdown"
      :class="{ visible: modelDropdownVisible }"
      @click="closeModelDropdown"
    >
      <!-- Остановка всплытия клика, чтобы нажатие на кнопки не закрывало список раньше времени -->
      <div class="gpt-model-select-container" @click.stop>
        <button
          class="gpt-model-select-item"
          :class="{ active: model.id === currentModelId }"
          v-for="(model, index) in models"
          :key="index"
          @click="selectModel(model)"
        >
          <div class="gpt-model-select-text">
            <div class="gpt-model-select-modelname" v-html="model.name"></div>
            <div class="gpt-model-select-description">
              {{ model.description }}
            </div>
          </div>
          <div class="gpt-model-select-logo">
            <!-- Текстовые модели: chat-иконка -->
            <svg
              v-if="['gpt-5.4-nano', 'gpt-4o', 'gpt-5.4-mini'].includes(model.id)"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M19 8H18V5C18 4.20435 17.6839 3.44129 17.1213 2.87868C16.5587 2.31607 15.7956 2 15 2H5C4.20435 2 3.44129 2.31607 2.87868 2.87868C2.31607 3.44129 2 4.20435 2 5V17C2.00099 17.1974 2.06039 17.3901 2.17072 17.5539C2.28105 17.7176 2.43738 17.845 2.62 17.92C2.73868 17.976 2.86882 18.0034 3 18C3.13161 18.0008 3.26207 17.9755 3.38391 17.9258C3.50574 17.876 3.61656 17.8027 3.71 17.71L6.52 14.89H8V16.33C8 17.1256 8.31607 17.8887 8.87868 18.4513C9.44129 19.0139 10.2044 19.33 11 19.33H17.92L20.29 21.71C20.3834 21.8027 20.4943 21.876 20.6161 21.9258C20.7379 21.9755 20.8684 22.0008 21 22C21.1312 22.0034 21.2613 21.976 21.38 21.92C21.5626 21.845 21.7189 21.7176 21.8293 21.5539C21.9396 21.3901 21.999 21.1974 22 21V11C22 10.2044 21.6839 9.44129 21.1213 8.87868C20.5587 8.31607 19.7956 8 19 8ZM8 11V12.89H6.11C5.97839 12.8892 5.84793 12.9145 5.72609 12.9642C5.60426 13.014 5.49344 13.0873 5.4 13.18L4 14.59V5C4 4.73478 4.10536 4.48043 4.29289 4.29289C4.48043 4.10536 4.73478 4 5 4H15C15.2652 4 15.5196 4.10536 15.7071 4.29289C15.8946 4.48043 16 4.73478 16 5V8H11C10.2044 8 9.44129 8.31607 8.87868 8.87868C8.31607 9.44129 8 10.2044 8 11ZM20 18.59L19 17.59C18.9074 17.4955 18.7969 17.4203 18.6751 17.3688C18.5532 17.3173 18.4223 17.2906 18.29 17.29H11C10.7348 17.29 10.4804 17.1846 10.2929 16.9971C10.1054 16.8096 10 16.5552 10 16.29V11C10 10.7348 10.1054 10.4804 10.2929 10.2929C10.4804 10.1054 10.7348 10 11 10H19C19.2652 10 19.5196 10.1054 19.7071 10.2929C19.8946 10.4804 20 10.7348 20 11V18.59Z"
                fill="currentColor"
              ></path>
              <!-- Изменено -->
            </svg>
            <!-- Условный рендеринг для GPT Image -->
            <svg
              v-else-if="model.id === 'gpt-image-1.5'"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M19 2H5C4.20435 2 3.44129 2.31607 2.87868 2.87868C2.31607 3.44129 2 4.20435 2 5V19C2 19.7956 2.31607 20.5587 2.87868 21.1213C3.44129 21.6839 4.20435 22 5 22H19C19.1645 21.9977 19.3284 21.981 19.49 21.95L19.79 21.88H19.86H19.91L20.28 21.74L20.41 21.67C20.51 21.61 20.62 21.56 20.72 21.49C20.8535 21.3918 20.9805 21.2849 21.1 21.17L21.17 21.08C21.2682 20.9805 21.3585 20.8735 21.44 20.76L21.53 20.63C21.5998 20.5187 21.6601 20.4016 21.71 20.28C21.7374 20.232 21.7609 20.1818 21.78 20.13C21.83 20.01 21.86 19.88 21.9 19.75V19.6C21.9567 19.4046 21.9903 19.2032 22 19V5C22 4.20435 21.6839 3.44129 21.1213 2.87868C20.5587 2.31607 19.7956 2 19 2ZM5 20C4.73478 20 4.48043 19.8946 4.29289 19.7071C4.10536 19.5196 4 19.2652 4 19V14.69L7.29 11.39C7.38296 11.2963 7.49356 11.2219 7.61542 11.1711C7.73728 11.1203 7.86799 11.0942 8 11.0942C8.13201 11.0942 8.26272 11.1203 8.38458 11.1711C8.50644 11.2219 8.61704 11.2963 8.71 11.39L17.31 20H5ZM20 19C19.9991 19.1233 19.9753 19.2453 19.93 19.36C19.9071 19.4087 19.8804 19.4556 19.85 19.5C19.8232 19.5423 19.7931 19.5825 19.76 19.62L14.41 14.27L15.29 13.39C15.383 13.2963 15.4936 13.2219 15.6154 13.1711C15.7373 13.1203 15.868 13.0942 16 13.0942C16.132 13.0942 16.2627 13.1203 16.3846 13.1711C16.5064 13.2219 16.617 13.2963 16.71 13.39L20 16.69V19ZM20 13.86L18.12 12C17.5477 11.457 16.7889 11.1543 16 11.1543C15.2111 11.1543 14.4523 11.457 13.88 12L13 12.88L10.12 10C9.54772 9.45699 8.7889 9.15428 8 9.15428C7.2111 9.15428 6.45228 9.45699 5.88 10L4 11.86V5C4 4.73478 4.10536 4.48043 4.29289 4.29289C4.48043 4.10536 4.73478 4 5 4H19C19.2652 4 19.5196 4.10536 19.7071 4.29289C19.8946 4.48043 20 4.73478 20 5V13.86ZM13.5 6C13.2033 6 12.9133 6.08797 12.6666 6.2528C12.42 6.41762 12.2277 6.65189 12.1142 6.92597C12.0006 7.20006 11.9709 7.50166 12.0288 7.79264C12.0867 8.08361 12.2296 8.35088 12.4393 8.56066C12.6491 8.77044 12.9164 8.9133 13.2074 8.97118C13.4983 9.02906 13.7999 8.99935 14.074 8.88582C14.3481 8.77229 14.5824 8.58003 14.7472 8.33335C14.912 8.08668 15 7.79667 15 7.5C15 7.10218 14.842 6.72064 14.5607 6.43934C14.2794 6.15804 13.8978 6 13.5 6Z"
                fill="currentColor"
              ></path>
              <!-- Изменено -->
            </svg>
          </div>
        </button>
      </div>
    </div>

    <!-- Header -->
    <header>
      <div class="header__sidebar" v-ripple @click="router.push('/')">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M3 8.5H21"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          ></path>
          <!-- Изменено stroke на currentColor -->
          <path
            d="M3 15.5H16"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          ></path>
          <!-- Изменено stroke на currentColor -->
        </svg>
      </div>

      <!-- Обертка для центрирования -->
      <div class="header__model-wrapper">
        <div
          class="header__model"
          ref="modelSelector"
          @click="toggleModelDropdown"
        >
          <div class="header__model-name" v-html="selectedModel"></div>
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            :class="{ 'arrow-open': modelDropdownVisible }"
          >
            <path
              d="M16 10L12 14L8 10"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            ></path>
          </svg>
        </div>
      </div>

      <div class="header__limits"></div>
    </header>

    <!-- Область чата -->
    <div class="chat-wrapper">
      <div
        class="chat-content"
        :class="{
          empty: chatMessages.length === 0,
          'chat-content--restoring': isReturningFromSettings,
        }"
        ref="chatContent"
        @scroll="onChatScroll"
      >
        <!-- Load more button shown when there are older messages -->
        <div v-if="hasMoreToLoad && chatMessages.length" class="load-more-row">
          <button
            class="load-more-btn"
            :class="{ 'load-more-btn--loading': isLoadingOlderMessages }"
            :disabled="isLoadingOlderMessages"
            @click="loadOlderMessages"
          >
            {{
              isLoadingOlderMessages
                ? $t("load_more_loading")
                : $t("load_more_messages")
            }}
          </button>
        </div>
        <!-- Если сообщений ещё нет, показ пустой карточки (но не во время загрузки диалога) -->
        <template v-if="chatMessages.length === 0 && !isDialogLoading">
          <div class="ui-emptyChatCard">
            <div class="ui-ecc-title">{{ $t("empty_chat") }}</div>
            <div class="ui-ecc-text">
              {{
                currentModelId === "gpt-image-1.5"
                  ? $t("describe_image")
                  : $t("send_message")
              }}
            </div>
            <div style="width: 112px; height: 112px">
              <!-- Здесь показ случайной обезьянки -->
              <img :src="emptyCardImage" alt="Пустой чат" draggable="false" class="empty-card-img" />
            </div>
          </div>
        </template>
        <!-- Иначе вывод списка сообщений -->
        <template v-else>
          <template v-for="(msg, index) in chatMessages" :key="index">
            <div
              class="msg-group"
              :class="msg.type === 'user' ? 'msg-group--user' : 'msg-group--bot'"
            >
            <!-- Фото пользователя - отдельным блоком над пузырём, без фона -->
            <div
              v-if="msg.type === 'user' && msg.imageUrl"
              class="user-photo"
              :class="{ 'user-photo--sized': !!(msg.imageW && msg.imageH) }"
              :style="photoStyle(msg)"
            >
              <div
                v-if="!msg.localUrl && !loadedImages.has(msg.imageUrl) && !!msg.imageW"
                class="user-photo-skeleton"
              ></div>
              <img
                :src="msg.localUrl || msg.imageUrl"
                alt=""
                class="user-photo-img"
                @load="onImageLoad(msg.imageUrl!)"
                @error="loadedImages.add(msg.imageUrl!)"
                @click="openFullImage(msg.localUrl || msg.imageUrl || '')"
              />
            </div>

            <!-- Пузырь: бот всегда; пользователь - только если есть текст -->
            <div
              v-if="msg.type !== 'user' || msg.text"
              :class="[
                'message',
                msg.type === 'user' ? 'user-message' : 'bot-message',
              ]"
            >
              <!-- Сообщение пользователя -->
              <span v-if="msg.type === 'user'">{{ msg.text }}</span>

              <!-- Сообщение бота с обработкой разных типов контента -->
              <div v-else>
              <!-- Для изображений -->
              <div v-if="msg.contentType === 'image'">
                <p v-if="msg.text">{{ msg.text }}</p>
                <div class="image-container">
                  <ChatLoader
                    v-if="msg.imageUrl && !loadedImages.has(msg.imageUrl)"
                    variant="image"
                  />
                  <img
                    v-if="msg.imageUrl"
                    :src="msg.imageUrl"
                    alt=""
                    class="generated-image"
                    :class="{
                      'image-loading': !loadedImages.has(msg.imageUrl ?? ''),
                    }"
                    @load="onImageLoad(msg.imageUrl!)"
                    @error="loadedImages.add(msg.imageUrl!)"
                    @click="openFullImage(msg.imageUrl ?? '')"
                  />
                </div>
              </div>

              <!-- Для текста -->
              <div v-else-if="msg.type === 'bot'">
                <ChatLoader
                  v-if="index === streamingBotIdx && !msg.text"
                  variant="thinking"
                />
                <!-- Текст ответа -->
                <div v-if="msg.text" class="md-body" v-html="index === streamingBotIdx ? streamHtml : formatMessage(msg.text)" @click="onContentClick"></div>
                <!-- Кнопки: копировать / лайк / дизлайк / три точки - только когда генерация завершена -->
                <div
                  v-if="index !== streamingBotIdx && msg.text"
                  class="copy-wrapper"
                >
                  <!-- Копировать -->
                  <div
                    class="btn-tip-wrap"
                    :data-tip="
                      copiedIndex === index
                        ? t('tooltip_copied')
                        : t('tooltip_copy')
                    "
                  >
                    <button
                      class="copy-button"
                      :class="{ 'copied-state': copiedIndex === index }"
                      @click="copyToClipboard(msg.text, index)"
                    >
                      <svg
                        v-if="copiedIndex === index"
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 50 50"
                      >
                        <path
                          fill="currentColor"
                          d="M 41.9375 8.625 C 41.273438 8.648438 40.664063 9 40.3125 9.5625 L 21.5 38.34375 L 9.3125 27.8125 C 8.789063 27.269531 8.003906 27.066406 7.28125 27.292969 C 6.5625 27.515625 6.027344 28.125 5.902344 28.867188 C 5.777344 29.613281 6.078125 30.363281 6.6875 30.8125 L 20.625 42.875 C 21.0625 43.246094 21.640625 43.410156 22.207031 43.328125 C 22.777344 43.242188 23.28125 42.917969 23.59375 42.4375 L 43.6875 11.75 C 44.117188 11.121094 44.152344 10.308594 43.78125 9.644531 C 43.410156 8.984375 42.695313 8.589844 41.9375 8.625 Z"
                        />
                      </svg>
                      <svg
                        v-else
                        viewBox="0 0 20 20"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M7 7V4.2002C7 3.08009 7 2.51962 7.21799 2.0918C7.40973 1.71547 7.71547 1.40973 8.0918 1.21799C8.5196 1 9.0801 1 10.2002 1H15.8002C16.9203 1 17.4801 1 17.9079 1.21799C18.2842 1.40973 18.5905 1.71547 18.7822 2.0918C19.0002 2.51962 19.0002 3.07967 19.0002 4.19978V9.7998C19.0002 10.9199 19.0002 11.48 18.7822 11.9078C18.5905 12.2841 18.2839 12.5905 17.9076 12.7822C17.4802 13 16.921 13 15.8031 13H13M7 7H4.2002C3.08009 7 2.51962 7 2.0918 7.21799C1.71547 7.40973 1.40973 7.71547 1.21799 8.0918C1 8.5196 1 9.0801 1 10.2002V15.8002C1 16.9203 1 17.4801 1.21799 17.9079C1.40973 18.2842 1.71547 18.5905 2.0918 18.7822C2.5192 19 3.07899 19 4.19691 19H9.8036C10.9215 19 11.4805 19 11.9079 18.7822C12.2842 18.5905 12.5905 18.2839 12.7822 17.9076C13 17.4802 13 16.921 13 15.8031V13M7 7H9.8002C10.9203 7 11.4801 7 11.9079 7.21799C12.2842 7.40973 12.5905 7.71547 12.7822 8.0918C13 8.5192 13 9.079 13 10.1969V13"
                          stroke="currentColor"
                          stroke-width="2"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </svg>
                    </button>
                  </div>
                  <!-- Лайк -->
                  <div class="btn-tip-wrap" :data-tip="t('tooltip_like')">
                    <button
                      class="action-btn"
                      :class="{
                        'reacted-like': reactionMap.get(index) === 'like',
                      }"
                      @click="onReaction(index, 'like')"
                    >
                      <svg
                        viewBox="0 -960 960 960"
                        fill="currentColor"
                        width="16"
                        height="16"
                      >
                        <path
                          d="M720-120H280v-520l280-280 50 50q7 7 11.5 19t4.5 23v14l-44 174h258q32 0 56 24t24 56v80q0 7-2 15t-4 15L794-168q-9 20-30 34t-44 14Zm-360-80h360l120-280v-80H480l54-220-174 174v406Zm0-406v406-406Zm-80-34v80H160v360h120v80H80v-520h200Z"
                        />
                      </svg>
                    </button>
                  </div>
                  <!-- Дизлайк -->
                  <div class="btn-tip-wrap" :data-tip="t('tooltip_dislike')">
                    <button
                      class="action-btn"
                      :class="{
                        'reacted-dislike': reactionMap.get(index) === 'dislike',
                      }"
                      @click="onReaction(index, 'dislike')"
                    >
                      <svg
                        viewBox="0 -960 960 960"
                        fill="currentColor"
                        width="16"
                        height="16"
                        style="transform: scaleX(-1)"
                      >
                        <path
                          d="M240-840h440v520L400-40l-50-50q-7-7-11.5-19t-4.5-23v-14l44-174H120q-32 0-56-24t-24-56v-80q0-7 2-15t4-15l120-282q9-20 30-34t44-14Zm360 80H240L120-480v80h360l-54 220 174-174v-406Zm0 406v-406 406Zm80 34v-80h120v-360H680v-80h200v520H680Z"
                        />
                      </svg>
                    </button>
                  </div>
                  <!-- Три точки (экспорт) - только для ios/macos/tdesktop -->
                  <div v-if="canExport" class="btn-tip-wrap more-wrap">
                    <button
                      class="action-btn"
                      @click.stop="toggleMoreMenu(index, $event)"
                    >
                      <svg
                        viewBox="0 -960 960 960"
                        fill="currentColor"
                        width="16"
                        height="16"
                        style="transform: rotate(90deg)"
                      >
                        <path
                          d="M480-160q-33 0-56.5-23.5T400-240q0-33 23.5-56.5T480-320q33 0 56.5 23.5T560-240q0 33-23.5 56.5T480-160Zm0-240q-33 0-56.5-23.5T400-480q0-33 23.5-56.5T480-560q33 0 56.5 23.5T560-480q0 33-23.5 56.5T480-400Zm0-240q-33 0-56.5-23.5T400-720q0-33 23.5-56.5T480-800q33 0 56.5 23.5T560-720q0 33-23.5 56.5T480-640Z"
                        />
                      </svg>
                    </button>
                    <div
                      v-if="moreMenuIndex === index"
                      class="more-menu"
                      :class="{ upward: moreMenuUp }"
                      @click.stop
                    >
                      <button
                        class="more-menu-item"
                        @click="exportTxt(msg.text)"
                      >
                        {{ t("export_txt") }}
                      </button>
                      <button
                        class="more-menu-item"
                        @click="exportPdf(msg.text)"
                      >
                        {{ t("export_pdf") }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          </div>
          </template>
        </template>
        <!-- Spacer: replaces padding-bottom - fixes iOS Safari not including padding in scrollHeight -->
        <div class="chat-end-spacer"></div>
      </div>
    </div>

    <!-- Footer с полем ввода -->
    <Transition name="scroll-btn-fade">
      <button
        v-if="showScrollBtn && !isReturningFromSettings"
        class="scroll-to-bottom-btn"
        @click="scrollToBottomSmooth"
        aria-label="Scroll to bottom"
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          style="pointer-events: none; user-select: none; display: block"
        >
          <path
            d="M6 9L12 15L18 9"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
    </Transition>
    <footer>
      <!-- Панель «+» (пока только Галерея; на будущее - файлы и т.д.) -->
      <Transition name="attach-panel">
        <div v-if="attachPanelOpen" class="attach-panel" @click.stop>
          <button
            type="button"
            class="attach-panel-item"
            @click="pickGallery"
          >
            <svg viewBox="0 -960 960 960" width="22" height="22" fill="currentColor">
              <path d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320l-90-120-120 160Z" />
            </svg>
            <span>{{ $t('gallery') }}</span>
          </button>
        </div>
      </Transition>

      <!-- off-screen, не hidden - иначе iOS не открывает пикер -->
      <input
        ref="galleryInput"
        type="file"
        accept="image/*"
        class="composer-file-input"
        @change="onFileChange"
      />

      <form class="footer__input" @submit.prevent="sendMessage">
        <div
          class="input__text null"
          :class="{ 'has-attach': !!attachment, 'composer--stacked': composerStacked }"
        >
          <!-- Превью прикреплённого фото - над строкой ввода -->
          <div v-if="attachment" class="attach-preview">
            <div
              class="attach-thumb-wrap"
              :class="{ 'is-loading': attachment.status === 'uploading' }"
            >
              <img :src="attachment.preview" alt="" class="attach-thumb" />
              <div
                v-if="attachment.status === 'uploading'"
                class="attach-progress"
              >
                <svg viewBox="0 0 40 40" class="attach-ring">
                  <circle class="attach-ring-bg" cx="20" cy="20" r="16" />
                  <circle
                    class="attach-ring-fg"
                    cx="20"
                    cy="20"
                    r="16"
                    :stroke-dasharray="ringCircumference"
                    :stroke-dashoffset="ringOffset"
                  />
                </svg>
              </div>
              <div v-else-if="attachment.status === 'error'" class="attach-failed">!</div>
              <div class="input__text-image-delete" @click="removeAttachment">
                <svg viewBox="0 -960 960 960" width="10" height="10" fill="currentColor">
                  <path d="m256-200-56-56 224-224-224-224 56-56 224 224 224-224 56 56-224 224 224 224-56 56-224-224-224 224Z" />
                </svg>
              </div>
            </div>
          </div>

          <!-- Строка: [+] · текст · [↑] -->
          <div class="composer-row">
            <button
              v-if="!isImageModel"
              v-ripple
              type="button"
              class="input__attach"
              :class="{ disabled: !!attachment }"
              :disabled="!!attachment"
              @click.stop="toggleAttachPanel"
              aria-label="attach"
            >
              <svg viewBox="0 -960 960 960" width="22" height="22" fill="currentColor">
                <path d="M440-440H200v-80h240v-240h80v240h240v80H520v240h-80v-240Z" />
              </svg>
            </button>

            <div class="composer-text">
              <div
                id="editable-message-text"
                contenteditable="true"
                role="textbox"
                dir="ltr"
                ref="editableDiv"
                @input="onInput"
                @paste.prevent="onPaste"
                @dragover.prevent
                @drop.prevent
              ></div>
              <span
                v-if="messageText.trim() === ''"
                class="input__text-placeholder"
              >
                {{ inputPlaceholder }}
              </span>
            </div>

            <label
              class="input__submit"
              :class="{ disabled: isSubmitDisabled }"
              :style="isSubmitDisabled ? { pointerEvents: 'none' } : {}"
            >
              <button
                :disabled="isSubmitDisabled"
                id="chat__input-submitbutton"
                type="submit"
              ></button>
              <!-- Инлайн SVG для СТРЕЛКИ ВВЕРХ -->
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M12 19V5M5 12L12 5L19 12"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </label>
          </div>
        </div>
      </form>
    </footer>

    <!-- Модальное окно для просмотра изображений -->
    <div v-if="showFullImage" class="image-modal" @click="closeFullImage">
      <img :src="fullImageUrl" alt="" />
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  onActivated,
  onDeactivated,
  nextTick,
  watch,
  reactive,
} from "vue";
import { useI18n } from "vue-i18n";
import { useRouter, useRoute } from "vue-router";
import { retrieveLaunchParams, viewport, openLink } from "@tma.js/sdk-vue";
import { api, wsClient, BASE_URL, LimitError } from "@/services/api";
import { outbox } from "@/services/outbox";
import {
  useUserStore,
  dialogMessagesToChat,
  type ChatMessage,
} from "@/store/user";
import { useDialogsStore } from "@/store/dialogs";
import { useImagesStore } from "@/store/images";
import ChatLoader from "@/components/ChatLoader.vue";
import { markdownReady, renderMarkdownSafe, preloadMarkdown } from "@/utils/markdownReady";

defineOptions({ name: "ChatPage" });

// Импорт изображений
import monkeyChemistry from "@/components/img/monkey/chemistry.svg";
import monkeyHacker from "@/components/img/monkey/hacker.svg";
import monkeyHappy from "@/components/img/monkey/happy.svg";
import monkeyIdea from "@/components/img/monkey/idea.svg";
import monkeyQuestion from "@/components/img/monkey/question.svg";
import monkeyRead from "@/components/img/monkey/read.svg";
import monkeyShock from "@/components/img/monkey/shock.svg";
import monkeyWork from "@/components/img/monkey/work.svg";
import monkeyWorkout from "@/components/img/monkey/workout.svg";

interface ModelOption {
  id: string;
  name: string;
  description: string;
}

const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const store = useUserStore();
const dialogsStore = useDialogsStore();
const imagesStore = useImagesStore();

const copiedIndex = ref<number | null>(null);
const reactionMap = reactive(new Map<number, "like" | "dislike">());
const moreMenuIndex = ref<number | null>(null);
const moreMenuUp = ref(false);
const streamingBotIdx = ref(-1);
/** reqId of a request whose WS dropped mid-generation; null if none. */
const pendingReconnectReqId = ref<string | null>(null);
/** chatMessages index of the bot slot waiting for reconnect. */
const pendingReconnectBotIdx = ref(-1);
/** True when the pending reconnect is an image request (vs text). */
const pendingReconnectIsImage = ref(false);
/** Set to true after the first loadChatHistory() completes. */
const initialLoadDone = ref(false);
/** True while a bootstrapDialog fetch is in-flight - prevents concurrent duplicate calls. */
let isLoadingHistory = false;
/** True while the offline outbox is being flushed - prevents concurrent flushes. */
let flushingOutbox = false;
let copyTimeout: ReturnType<typeof setTimeout> | null = null;
let suppressScrollEvents = false;
/**
 * True while the scroll-to-bottom button is animating a programmatic smooth scroll.
 * While active, onChatScroll keeps the button hidden so intermediate frames of a long
 * smooth scroll can't toggle it back on (the flicker bug).
 */
let smoothScrollActive = false;
/** Watchdog timer that drives the smooth-scroll completion check. */
let smoothScrollWatchdog: ReturnType<typeof setTimeout> | null = null;

/** True when the chat scroll is near the bottom (< 150px). Auto-scroll is only done here. */
const isNearBottom = ref(true);
/** True when user scrolled more than 100px from bottom - shows the scroll-to-bottom button. */
const showScrollBtn = ref(false);
/** True during first frame after returning from Settings to prevent stale button flash. */
const isReturningFromSettings = ref(false);
/**
 * Last scroll position recorded on a real user scroll. Captured continuously
 * (NOT in onDeactivated) because KeepAlive detaches the chat DOM on navigation,
 * which resets scrollTop to 0 before onDeactivated runs. null = user never
 * scrolled > fall back to bottom on return from Settings.
 */
let savedScrollTop: number | null = null;
/** True for platforms that support file export (iOS, macOS, tdesktop). */
const canExport = computed(() => {
  try {
    const p = retrieveLaunchParams().tgWebAppPlatform ?? "";
    return p === "ios" || p === "macos" || p === "tdesktop";
  } catch {
    return false;
  }
});
/** Cursor for the next Load-more call (next_before_index from backend). 0 = no more. */
const cursorIdx = ref(0);
/** True once the user has loaded at least one older page. */
const hasLoadedOlderPages = ref(false);
/** True while an older-messages page fetch is in-flight. */
const isLoadingOlderMessages = ref(false);
/** True when the server likely has older messages not yet loaded into view. */
const hasMoreToLoad = ref(false);
/** Watchdog: interval ID for zombie-WS detection during generation. */
let generationWatchdog: ReturnType<typeof setInterval> | null = null;

/* Просмотр изображений */
const fullImageUrl = ref("");
const showFullImage = ref(false);
// Tracks which image URLs have finished loading > used to show/hide skeleton.
const loadedImages = reactive(new Set<string>());

function openFullImage(url: string) {
  fullImageUrl.value = url;
  showFullImage.value = true;
  document.body.style.overflow = "hidden";
}

function closeFullImage() {
  showFullImage.value = false;
  fullImageUrl.value = "";
  document.body.style.overflow = "auto";
}

/** Фиксированный бокс фото в ленте по сохранённым размерам - скелетон 1:1, без рывка. */
function photoStyle(msg: ChatMessage): Record<string, string> {
  const w = msg.imageW;
  const h = msg.imageH;
  if (!w || !h) return {};
  const displayW = Math.min(300, (380 * w) / h);
  return { aspectRatio: `${w} / ${h}`, width: `${Math.round(displayW)}px` };
}

/* Прикрепление фото (vision) */
interface Attachment {
  preview: string;
  status: "uploading" | "ready" | "error";
  progress: number;
  url?: string;
  w: number;
  h: number;
}
const attachment = ref<Attachment | null>(null);
const attachPanelOpen = ref(false);
const galleryInput = ref<HTMLInputElement | null>(null);
const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;
// текст занял >1 строки > кнопки уходят вниз (ChatGPT). Замер стабильный (фикс. ширина).
const composerStacked = ref(false);

const isImageModel = computed(() => currentModelId.value === "gpt-image-1.5");

const ringCircumference = 2 * Math.PI * 16;
const ringOffset = computed(() =>
  attachment.value
    ? ringCircumference * (1 - attachment.value.progress)
    : ringCircumference,
);

function toggleAttachPanel() {
  if (attachment.value) return;
  attachPanelOpen.value = !attachPanelOpen.value;
}

function pickGallery() {
  // синхронно в жесте - иначе iOS не откроет пикер
  galleryInput.value?.click();
  attachPanelOpen.value = false;
}

function removeAttachment() {
  attachment.value = null;
}

function resizeToJpeg(
  file: File,
  maxSide: number,
  quality: number,
): Promise<{ b64: string; dataUrl: string; w: number; h: number }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("read error"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("decode error"));
      img.onload = () => {
        const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
        const w = Math.max(1, Math.round(img.width * scale));
        const h = Math.max(1, Math.round(img.height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("no canvas ctx"));
          return;
        }
        ctx.drawImage(img, 0, 0, w, h);
        const dataUrl = canvas.toDataURL("image/jpeg", quality);
        resolve({ dataUrl, b64: dataUrl.split(",", 2)[1] ?? "", w, h });
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  });
}

async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = ""; // повторный выбор того же файла
  if (!file) return;
  if (file.size > MAX_UPLOAD_BYTES) return; // >8 МБ - молча игнор

  let resized: { b64: string; dataUrl: string; w: number; h: number };
  try {
    resized = await resizeToJpeg(file, 1536, 0.92);
  } catch {
    return;
  }

  attachment.value = {
    preview: resized.dataUrl,
    status: "uploading",
    progress: 0,
    w: resized.w,
    h: resized.h,
  };
  try {
    const { url } = await api.uploadImage(resized.b64, (r) => {
      if (attachment.value) attachment.value.progress = r;
    });
    if (attachment.value) {
      attachment.value.url = url;
      attachment.value.status = "ready";
      attachment.value.progress = 1;
    }
  } catch {
    if (attachment.value) attachment.value.status = "error";
  }
}

/* Выбор модели */
const models = computed<ModelOption[]>(() => [
  {
    id: "gpt-5.4-nano",
    name: "GPT 5.4 <span>Nano</span>",
    description: t("for_everyday_tasks"),
  },
  {
    id: "gpt-4o",
    name: "GPT 4 <span>Omni</span>",
    description: t("for_complex_tasks"),
  },
  {
    id: "gpt-5.4-mini",
    name: "GPT 5.4 <span>Mini</span>",
    description: t("for_complex_tasks"),
  },
  {
    id: "gpt-image-1.5",
    name: "GPT 1.5 <span>Image</span>",
    description: t("generate_images"),
  },
]);

const currentModelId = ref(store.currentModel);
const selectedModel = ref(
  models.value.find((m) => m.id === currentModelId.value)?.name ??
    models.value[0].name,
);
const modelDropdownVisible = ref(false);
const modelSelector = ref<HTMLElement | null>(null);
const modelDropdown = ref<HTMLElement | null>(null);

// Синхронизация модели после загрузки store.init() (модель берётся из БД)
watch(
  () => store.currentModel,
  (newModel) => {
    const found = models.value.find((m) => m.id === newModel);
    if (found && found.id !== currentModelId.value) {
      currentModelId.value = found.id;
      selectedModel.value = found.name;
    }
  },
);

const inputPlaceholder = computed(() =>
  currentModelId.value === "gpt-image-1.5"
    ? t("input_placeholder_image")
    : t("input_placeholder_chat"),
);

function toggleModelDropdown(e: MouseEvent) {
  e.stopPropagation();
  modelDropdownVisible.value = !modelDropdownVisible.value;
}

function closeModelDropdown() {
  modelDropdownVisible.value = false;
}

async function selectModel(model: ModelOption) {
  if (model.id === currentModelId.value) return;
  const prevId = currentModelId.value;
  const prevName = selectedModel.value;
  currentModelId.value = model.id;
  selectedModel.value = model.name;
  if (model.id === "gpt-image-1.5") {
    attachment.value = null;
    attachPanelOpen.value = false;
  }
  try {
    await store.setModel(model.id);
  } catch {
    // DB save failed - rollback UI to previous selection.
    currentModelId.value = prevId;
    selectedModel.value = prevName;
  }
}

function handleDocumentClick(e: MouseEvent) {
  if (modelSelector.value && modelDropdown.value) {
    if (
      !modelSelector.value.contains(e.target as Node) &&
      !modelDropdown.value.contains(e.target as Node)
    ) {
      modelDropdownVisible.value = false;
    }
  }
  moreMenuIndex.value = null;
  attachPanelOpen.value = false;
}

/* Чат */
const messageText = ref("");
const chatMessages = ref<ChatMessage[]>(
  store.chatHistoryPrefetchOk ? [...store.chatHistory] : [],
);
const editableDiv = ref<HTMLElement | null>(null);
const chatContent = ref<HTMLElement | null>(null);

const isStreaming = computed(() => streamingBotIdx.value !== -1);
// фото прикреплено, но ещё грузится / упало - отправку блокируем
const attachBlocking = computed(
  () => !!attachment.value && attachment.value.status !== "ready",
);

/* Лимит: серая кнопка до сброса (раздельно msg / image, разное время сброса) */
const limitedMsgUntil = ref(0); // ms timestamp; 0 = нет лимита
const limitedImgUntil = ref(0);
const nowTick = ref(Date.now());
let limitTimer: ReturnType<typeof setInterval> | null = null;
const isLimited = computed(
  () =>
    nowTick.value <
    (isImageModel.value ? limitedImgUntil.value : limitedMsgUntil.value),
);

function startLimitCountdown(kind: string, retryAfterSec: number) {
  const until = Date.now() + Math.max(1, retryAfterSec) * 1000;
  if (kind === "image_gen") limitedImgUntil.value = until;
  else limitedMsgUntil.value = until;
  nowTick.value = Date.now();
  if (limitTimer) clearInterval(limitTimer);
  limitTimer = setInterval(() => {
    nowTick.value = Date.now();
    if (
      nowTick.value >= limitedMsgUntil.value &&
      nowTick.value >= limitedImgUntil.value &&
      limitTimer
    ) {
      clearInterval(limitTimer);
      limitTimer = null;
    }
  }, 1000);
}

const isSubmitDisabled = computed(
  () =>
    messageText.value.trim() === "" ||
    isStreaming.value ||
    attachBlocking.value ||
    isLimited.value,
);

/**
 * Maps req_id > chatMessages index for bot responses initiated on ANOTHER device.
 * Used by multi-device type handlers to update the correct message slot.
 */
const remoteBotSlots = new Map<string, number>();

// Скрытое «зеркало» для замера высоты текста на ФИКСИРОВАННОЙ (инлайн) ширине -
// решение «1 строка / много» не зависит от текущей раскладки > без флип-флопа.
let composerMirror: HTMLDivElement | null = null;

function updateComposerLayout() {
  const editable = editableDiv.value;
  if (!editable) return;
  const txt = editable.innerText;
  if (!txt.trim()) {
    composerStacked.value = false;
    return;
  }
  const row = editable.closest(".composer-row") as HTMLElement | null;
  if (!row) return;

  // точная ширина текста в ИНЛАЙНЕ = строка − паддинги − «+» − «↑» − гэпы − паддинг текста
  const rowCS = getComputedStyle(row);
  const gap = parseFloat(rowCS.columnGap) || 0;
  const rowInner =
    row.clientWidth -
    (parseFloat(rowCS.paddingLeft) + parseFloat(rowCS.paddingRight) || 0);
  const attachEl = row.querySelector(".input__attach") as HTMLElement | null;
  const sendEl = row.querySelector(".input__submit") as HTMLElement | null;
  const attachW = attachEl ? attachEl.offsetWidth : 0;
  const sendW = sendEl ? sendEl.offsetWidth : 0;
  const cs = getComputedStyle(editable);
  const editPad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) || 0;
  // 3 колонки > всегда 2 гэпа, даже когда «+» отсутствует (gpt-image)
  const textW = Math.max(20, rowInner - attachW - sendW - gap * 2 - editPad);
  const lh =
    cs.lineHeight === "normal"
      ? parseFloat(cs.fontSize) * 1.2
      : parseFloat(cs.lineHeight) || 22;

  if (!composerMirror) {
    composerMirror = document.createElement("div");
    composerMirror.style.cssText =
      "position:absolute;left:-9999px;top:0;visibility:hidden;pointer-events:none;" +
      "white-space:pre-wrap;word-break:break-word;overflow-wrap:break-word;box-sizing:content-box;padding:0;";
    document.body.appendChild(composerMirror);
  }
  composerMirror.style.width = `${textW}px`;
  composerMirror.style.fontFamily = cs.fontFamily;
  composerMirror.style.fontSize = cs.fontSize;
  composerMirror.style.fontWeight = cs.fontWeight;
  composerMirror.style.letterSpacing = cs.letterSpacing;
  composerMirror.style.lineHeight = cs.lineHeight;
  composerMirror.textContent = txt;

  // запас 0.5 строки - переключаемся ровно когда реально появляется 2-я строка
  composerStacked.value = composerMirror.scrollHeight > lh * 1.5;
}

function onInput(e: Event) {
  messageText.value = (e.target as HTMLElement).innerText;
  updateComposerLayout();
}

/**
 * Paste only plain text into contenteditable.
 * Uses Selection API (not deprecated execCommand) - works on iOS, Android, desktop.
 * Prevents rich-text / HTML from clipboard importing foreign font-size/family styles.
 */
function onPaste(e: ClipboardEvent) {
  const text = e.clipboardData?.getData("text/plain") ?? "";
  if (!text) return;
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return;
  const range = sel.getRangeAt(0);
  range.deleteContents(); // delete any currently selected text
  const node = document.createTextNode(text);
  range.insertNode(node);
  range.setStartAfter(node); // move cursor to end of inserted text
  range.collapse(true);
  sel.removeAllRanges();
  sel.addRange(range);
  messageText.value =
    (editableDiv.value as HTMLElement | null)?.innerText ?? "";
  updateComposerLayout();
}

function scrollToBottom() {
  // Hide the scroll button immediately - this is a programmatic autoscroll.
  showScrollBtn.value = false;
  isNearBottom.value = true;
  // Do NOT set suppressScrollEvents here: on mobile/Telegram WebView, rAF can be
  // delayed by seconds during initialisation. Suppressing scroll events for that
  // whole window would silently ignore the user's manual scroll and then forcibly
  // throw them back to the bottom when the frame finally fires.
  requestAnimationFrame(() => {
    const el = chatContent.value;
    if (!el) return;
    // Check actual DOM position - the user may have scrolled up while this frame
    // was pending (isNearBottom is stale because events were not suppressed).
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distFromBottom > 150) {
      // User scrolled away - respect their position instead of overriding it.
      isNearBottom.value = false;
      showScrollBtn.value = true;
      return;
    }
    suppressScrollEvents = true;
    el.scrollTop = el.scrollHeight;
    suppressScrollEvents = false;
    onChatScroll();
  });
}

/**
 * Immediate non-animated jump to bottom used after returning from Settings.
 * Avoids scroll-button flash and visual reflow jitter.
 */
function jumpToBottomSilent() {
  const el = chatContent.value;
  if (!el) return;
  suppressScrollEvents = true;
  el.scrollTop = el.scrollHeight;
  isNearBottom.value = true;
  showScrollBtn.value = false;
  suppressScrollEvents = false;
}

function onImageLoad(url: string) {
  loadedImages.add(url);
  if (isNearBottom.value) jumpToBottomSilent();
}

/** Finish a programmatic smooth scroll: stop the watchdog and recompute button state. */
function endSmoothScroll() {
  if (smoothScrollWatchdog !== null) {
    clearTimeout(smoothScrollWatchdog);
    smoothScrollWatchdog = null;
  }
  smoothScrollActive = false;
  // Recompute final button/isNearBottom state from the real DOM position.
  onChatScroll();
}

/**
 * Smooth scroll to bottom - used by the scroll-to-bottom button.
 *
 * Instead of a fixed 600 ms timer (which fires mid-animation on long scrolls and makes
 * the button flicker back on), we keep the button hidden via smoothScrollActive and poll
 * until the scroll genuinely reaches the bottom, settles, the user grabs it, or we time out.
 */
function scrollToBottomSmooth() {
  const el = chatContent.value;
  if (!el) return;
  showScrollBtn.value = false;
  isNearBottom.value = true;

  // Restart cleanly if a previous smooth scroll was still in flight.
  if (smoothScrollWatchdog !== null) {
    clearTimeout(smoothScrollWatchdog);
    smoothScrollWatchdog = null;
  }
  smoothScrollActive = true;
  el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });

  const startedAt = Date.now();
  let lastDist = Number.POSITIVE_INFINITY;
  let stable = 0;
  const poll = () => {
    const node = chatContent.value;
    if (!node) {
      smoothScrollActive = false;
      smoothScrollWatchdog = null;
      return;
    }
    const dist = node.scrollHeight - node.scrollTop - node.clientHeight;
    // Reached the bottom, or safety timeout - done.
    if (dist < 4 || Date.now() - startedAt > 3000) {
      endSmoothScroll();
      return;
    }
    // Moving AWAY from the bottom > the user grabbed the scroll. Respect them.
    if (dist > lastDist + 8) {
      endSmoothScroll();
      return;
    }
    // Position stopped changing but isn't exactly at the bottom (spacer/rounding) - settled.
    if (Math.abs(dist - lastDist) < 2) {
      if (++stable >= 3) {
        endSmoothScroll();
        return;
      }
    } else {
      stable = 0;
    }
    lastDist = dist;
    smoothScrollWatchdog = setTimeout(poll, 100);
  };
  smoothScrollWatchdog = setTimeout(poll, 100);
}

/** Scroll to bottom only when the user is already near the bottom. */
function scrollToBottomIfAtBottom() {
  if (isNearBottom.value) scrollToBottom();
}

/** Chat scroll event - tracks isNearBottom + triggers lazy-load when near top. */
function onChatScroll() {
  if (suppressScrollEvents) return;
  const el = chatContent.value;
  if (!el) return;
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
  isNearBottom.value = distFromBottom < 150;
  // While a programmatic smooth scroll is animating, keep the button hidden - don't let
  // intermediate frames toggle it back on (flicker fix). It's finalised in endSmoothScroll.
  if (!smoothScrollActive) {
    // Hysteresis: separate show (>120) and hide (<60) thresholds stop the button from
    // jittering on/off when the scroll position hovers around a single boundary.
    if (distFromBottom > 120) showScrollBtn.value = true;
    else if (distFromBottom < 60) showScrollBtn.value = false;
  }
  // Record the user's real position so we can restore it on return from Settings.
  savedScrollTop = el.scrollTop;
}

/* Загрузка истории из API */
function seedReactions() {
  reactionMap.clear();
  chatMessages.value.forEach((m, i) => {
    if (m.reaction) reactionMap.set(i, m.reaction);
  });
}

function applyChatHistory(messages: ChatMessage[]) {
  chatMessages.value = messages;
  store.setChatHistory(messages);
  seedReactions();
}

/** Lazy-load one page (20) of older messages and prepend without losing scroll position. */
async function loadOlderMessages() {
  if (!hasMoreToLoad.value || isLoadingOlderMessages.value || !store.dialogId)
    return;
  isLoadingOlderMessages.value = true;

  const el = chatContent.value;
  // Capture both height and scrollTop BEFORE any async work.
  const prevScrollHeight = el?.scrollHeight ?? 0;
  const prevScrollTop = el?.scrollTop ?? 0;

  try {
    const { messages, next_before_index, has_more } = await api.getMessagesPage(
      store.dialogId,
      cursorIdx.value,
    );
    if (messages.length === 0) {
      hasMoreToLoad.value = false;
      return;
    }
    const older = dialogMessagesToChat(messages);
    chatMessages.value = [...older, ...chatMessages.value];
    store.setChatHistory(chatMessages.value);
    seedReactions(); // индексы сместились после prepend
    cursorIdx.value = next_before_index;
    // Backend is the single source of truth for whether more pages exist.
    hasMoreToLoad.value = has_more;
    hasLoadedOlderPages.value = true;
    // Restore scroll: keep the same visual position (stable viewport after prepend).
    await nextTick();
    if (el) el.scrollTop = prevScrollTop + (el.scrollHeight - prevScrollHeight);
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      // HTTP/2 session teardown during WS reconnect - retry automatically after it settles.
      isLoadingOlderMessages.value = false;
      await new Promise((r) => setTimeout(r, 800));
      if (hasMoreToLoad.value) loadOlderMessages();
      return;
    }
    console.error("Ошибка загрузки старых сообщений:", e);
    // hasMoreToLoad stays true so the user can retry by pressing the button again.
  } finally {
    isLoadingOlderMessages.value = false;
  }
}

async function loadChatHistory(forceScroll = false) {
  // черновик - нечего загружать, bootstrap создал бы лишний диалог
  if (route.params.dialogId === "new") return;
  // Never overwrite an active stream - the spinner slots would be lost.
  if (streamingBotIdx.value !== -1) return;
  // If user has manually loaded older pages, skip reconnect refresh to preserve them.
  if (hasLoadedOlderPages.value && !forceScroll) return;
  // Deduplicate: set flag immediately (before any await) to prevent concurrent calls.
  if (isLoadingHistory) return;
  isLoadingHistory = true;

  try {
    // Уже подгружено на экране загрузки - не дублируем запросы (меньше abort / HTTP2).
    if (store.chatHistoryPrefetchOk && store.dialogId) {
      applyChatHistory([...store.chatHistory]);
      cursorIdx.value = store.chatHistoryNextCursor;
      hasMoreToLoad.value = store.chatHistoryNextCursor > 0;
      if (forceScroll) {
        await nextTick();
        jumpToBottomSilent();
      }
      return;
    }

    // Show cached messages immediately so the user sees content right away.
    const hadCachedData = store.chatHistory.length > 0;
    if (hadCachedData) {
      applyChatHistory([...store.chatHistory]);
      if (forceScroll) {
        await nextTick();
        jumpToBottomSilent();
      }
    }

    const { dialog_id, messages, next_before_index } =
      await api.bootstrapDialog();
    store.setDialogId(dialog_id);
    if (streamingBotIdx.value === -1) {
      // Measure the REAL distance from bottom BEFORE swapping content. A background
      // refresh (e.g. first connection_ack after WS connect) must not yank a user who
      // deliberately scrolled up even slightly - the 150px isNearBottom flag is too
      // lenient for that. Only re-pin to bottom on the initial load (forceScroll) or
      // when the user is genuinely pinned to the bottom (< 8px).
      const elBefore = chatContent.value;
      // scrollHeight/clientHeight are 0 on a KeepAlive-detached element - treat as "not at bottom"
      // to avoid spuriously scrolling the user down when they return from Settings.
      const attached = elBefore && elBefore.scrollHeight > 0;
      const wasAtBottom = attached
        ? elBefore.scrollHeight - elBefore.scrollTop - elBefore.clientHeight < 8
        : false;
      applyChatHistory(dialogMessagesToChat(messages ?? []));
      cursorIdx.value = next_before_index;
      hasMoreToLoad.value = next_before_index > 0;
      await nextTick();
      const el = chatContent.value;
      if (el) {
        if (forceScroll || wasAtBottom) {
          showScrollBtn.value = false;
          suppressScrollEvents = true;
          requestAnimationFrame(() => {
            el.scrollTop = el.scrollHeight;
            suppressScrollEvents = false;
            setTimeout(() => onChatScroll(), 0);
          });
        } else {
          // User scrolled up - preserve their position.
          setTimeout(() => onChatScroll(), 0);
        }
      }
    }
  } catch (e: unknown) {
    // AbortError is normal (tab navigation/close) - don't log it as an error.
    if (e instanceof DOMException && e.name === "AbortError") return;
    console.error("Ошибка при загрузке истории чата:", e);
  } finally {
    isLoadingHistory = false;
  }
}

/** True while switching to a known dialog - suppresses the empty "new chat" card flash. */
const isDialogLoading = ref(false);

/** Черновик: диалог не создан, появится в БД с первым сообщением. */
function openDraftChat() {
  streamingBotIdx.value = -1;
  remoteBotSlots.clear();
  pendingReconnectReqId.value = null;
  store.setDialogId(null);
  store.chatHistoryPrefetchOk = false;
  applyChatHistory([]);
  cursorIdx.value = 0;
  hasMoreToLoad.value = false;
  hasLoadedOlderPages.value = false;
}

/** Load a specific dialog by id (opened from Recents / page reload) and pin to bottom. */
async function loadDialogById(id: string) {
  if (isLoadingHistory) return;
  if (id === store.dialogId) {
    // тот же диалог + идёт генерация - не перезагружаем
    if (streamingBotIdx.value !== -1) return;
  } else {
    // переключение на другой диалог: бросаем незавершённую генерацию
    // (она досчитается и сохранится на сервере), чтобы не показывать старый диалог
    streamingBotIdx.value = -1;
    remoteBotSlots.clear();
    pendingReconnectReqId.value = null;
    applyChatHistory([]);
    isDialogLoading.value = true;
  }
  isLoadingHistory = true;
  try {
    store.setDialogId(id);
    store.chatHistoryPrefetchOk = false;
    const { messages, next_before_index } = await api.getMessagesPage(id, 999999, 20);
    applyChatHistory(dialogMessagesToChat(messages ?? []));
    cursorIdx.value = next_before_index;
    hasMoreToLoad.value = next_before_index > 0;
    hasLoadedOlderPages.value = false;
    // активным становится открытый диалог - reload вернёт именно его
    api.activateDialog(id).catch(() => {});
    await nextTick();
    jumpToBottomSilent();
  } catch (e) {
    console.error("Ошибка при загрузке диалога:", e);
  } finally {
    isLoadingHistory = false;
    isDialogLoading.value = false;
  }
}

/** Auto-generate an image when opened from the Images screen (?gen=prompt). */
function maybeAutoGenerate() {
  const gen = route.query.gen;
  if (typeof gen === "string" && gen) {
    currentModelId.value = "gpt-image-1.5";
    messageText.value = gen;
    if (editableDiv.value) editableDiv.value.innerText = gen;
    nextTick(() => sendMessage());
    router.replace({ name: "chat", params: { dialogId: route.params.dialogId } });
  }
}

/* Отправка сообщения */
async function sendMessage() {
  if (isStreaming.value) return;
  if (attachBlocking.value) return;
  if (isLimited.value) return; // лимит - не создаём диалог и не шлём
  const text = messageText.value.trim();
  if (!text) return;

  const ready = attachment.value?.status === "ready" ? attachment.value : null;
  const imageUrl = ready?.url;
  const localUrl = ready?.preview;
  const imageW = ready?.w;
  const imageH = ready?.h;

  // ленивое создание: диалог появляется только с первым сообщением
  let genDialogId = store.dialogId;
  const createdNewDialog = !genDialogId;
  if (!genDialogId) {
    try {
      const { dialog_id } = await api.newDialog();
      genDialogId = dialog_id;
      store.setDialogId(dialog_id);
      dialogsStore.prepend(dialog_id);
      router.replace({ name: "chat", params: { dialogId: dialog_id } });
    } catch (e) {
      console.error("[newDialog]", e);
      return;
    }
  }
  // генерация привязана к диалогу: если переключимся - UI этого диалога не трогаем
  const stillActive = () => store.dialogId === genDialogId;

  chatMessages.value.push({
    text,
    type: "user",
    contentType: imageUrl ? "image" : "text",
    imageUrl: imageUrl ?? null,
    localUrl: localUrl ?? null,
    imageW: imageW ?? null,
    imageH: imageH ?? null,
  });
  // фото уже у нас (localUrl) - скелетон не нужен (покажется только при перезагрузке истории)
  if (imageUrl) loadedImages.add(imageUrl);
  attachment.value = null;
  attachPanelOpen.value = false;
  messageText.value = "";
  composerStacked.value = false;
  if (editableDiv.value) editableDiv.value.innerText = "";
  // живое обновление времени диалога в списке (поднимается в «Сегодня»)
  if (genDialogId) dialogsStore.touch(genDialogId);

  await nextTick();
  scrollToBottom();

  const isImageModel = currentModelId.value === "gpt-image-1.5";
  chatMessages.value.push({ type: "bot", contentType: "text", text: "" });
  const botIdx = chatMessages.value.length - 1;
  resetStreamRender();
  streamingBotIdx.value = botIdx;

  // Start watchdog: if no server activity for 22 s while generating, force WS reconnect.
  // Handles "zombie" TCP connections where the OS hasn't closed the socket yet.
  if (generationWatchdog) clearInterval(generationWatchdog);
  generationWatchdog = setInterval(() => {
    if (streamingBotIdx.value === -1) {
      clearInterval(generationWatchdog!);
      generationWatchdog = null;
      return;
    }
    if (wsClient.msSinceLastServerMsg > 22_000) {
      wsClient.connect().catch(() => {});
    }
  }, 5_000);
  const myWatchdog = generationWatchdog;

  try {
    if (isImageModel) {
      // Image generation over WebSocket: progress events > no polling, no HTTP/2 PING issue.
      const result = await wsClient.generateImage(text, store.dialogId, () => {
        // Keep the empty bot slot (spinner) during both moderation and generation.
      });
      if (stillActive()) {
        if (result.dialog_id) store.setDialogId(result.dialog_id);
        chatMessages.value[botIdx] = {
          type: "bot",
          contentType: "image",
          imageUrl: result.url ?? "",
          text: "",
          id: result.id,
        };
      }
      // в галерею сразу, без перезагрузки
      if (result.url) {
        imagesStore.prepend({
          id: Date.now(),
          url: result.url,
          prompt: text,
          dialog_id: result.dialog_id ?? genDialogId ?? "",
          created_at: new Date().toISOString(),
        });
      }
    } else {
      // Text chat via WebSocket: chat_delta стримит накопленный текст.
      const result = await wsClient.chatStream(
        {
          message: text,
          dialog_id: genDialogId ?? undefined,
          model: currentModelId.value,
          chat_mode: store.user?.mini_app_chat_mode ?? "mini_app_assistant",
          image_url: imageUrl,
          image_w: imageW,
          image_h: imageH,
        },
        (delta) => {
          if (!stillActive() || !delta) return;
          chatMessages.value[botIdx] = { type: "bot", contentType: "text", text: delta };
          bumpStreamRender();
          nextTick().then(scrollToBottomIfAtBottom);
        },
      );
      if (stillActive()) {
        if (result.dialog_id) store.setDialogId(result.dialog_id);
        chatMessages.value[botIdx] = result.is_flagged
          ? { type: "bot", contentType: "text", text: t("message_flagged") }
          : { type: "bot", contentType: "text", text: result.answer, id: result.id };
      }
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    const reqId = (e as { reqId?: string }).reqId;
    if (e instanceof LimitError) {
      // лимит исчерпан: плашка в блоке ответа + серая кнопка с отсчётом
      const key =
        e.kind === "image_gen" ? "limit_images_reached" : "limit_messages_reached";
      const minutes = Math.max(1, Math.ceil(e.retryAfter / 60));
      if (stillActive()) {
        chatMessages.value[botIdx] = {
          type: "bot",
          contentType: "text",
          text: t(key, { limit: e.limit, minutes }),
        };
      }
      startLimitCountdown(e.kind, e.retryAfter);
      // первый отказ создал пустой диалог - откатываем, чтобы не висел "New Chat"
      if (createdNewDialog && genDialogId) {
        dialogsStore.remove(genDialogId).catch(() => {});
        store.setDialogId(null);
      }
    } else if (!stillActive()) {
      // переключились на другой диалог - результат досчитается на сервере, UI не трогаем
    } else if (msg === "network error" && reqId) {
      // WS dropped mid-generation (text or image) - keep the spinner and wait for reconnect.
      pendingReconnectReqId.value = reqId;
      pendingReconnectBotIdx.value = botIdx;
      pendingReconnectIsImage.value = isImageModel;
      // Fallback: show an error if we don't reconnect within 30 s.
      setTimeout(() => {
        if (pendingReconnectReqId.value !== reqId) return;
        chatMessages.value[pendingReconnectBotIdx.value] = {
          type: "bot",
          contentType: "text",
          text: t("error_response") + ": network error",
        };
        pendingReconnectReqId.value = null;
        pendingReconnectBotIdx.value = -1;
        streamingBotIdx.value = -1;
        store.setChatHistory(chatMessages.value);
      }, 30_000);
    } else if (msg === "network error") {
      outbox.enqueue({
        id: crypto.randomUUID(),
        kind: isImageModel ? "image" : "chat",
        body: {
          message: text,
          dialog_id: genDialogId ?? undefined,
          model: currentModelId.value,
          chat_mode: store.user?.mini_app_chat_mode ?? "mini_app_assistant",
          image_url: imageUrl,
          image_w: imageW,
          image_h: imageH,
        },
        localUrl: localUrl ?? null,
        createdAt: Date.now(),
      });
      chatMessages.value[botIdx] = {
        type: "bot",
        contentType: "text",
        text: "",
      };
    } else if (msg === "flagged") {
      chatMessages.value[botIdx] = {
        type: "bot",
        contentType: "text",
        text: t("message_flagged"),
      };
    } else {
      chatMessages.value[botIdx] = {
        type: "bot",
        contentType: "text",
        text: t("error_response") + ": " + msg,
      };
    }
  }

  if (generationWatchdog === myWatchdog) {
    clearInterval(myWatchdog);
    generationWatchdog = null;
  }
  // дальнейшее - только для активного диалога (иначе затрём состояние другого чата)
  if (!stillActive()) return;
  if (!pendingReconnectReqId.value) streamingBotIdx.value = -1;
  await nextTick();
  scrollToBottom(); // always scroll after own message receives a response
  store.setChatHistory(chatMessages.value);

  flushOutbox();
}

// последовательно: сервер допускает одну генерацию на диалог
async function flushOutbox(): Promise<void> {
  // не мешаем активной генерации - иначе серверный «already generating»
  if (flushingOutbox || !wsClient.connected || streamingBotIdx.value !== -1) return;
  if (outbox.size === 0) return;
  flushingOutbox = true;
  let touchedOpenDialog = false;
  try {
    for (const item of outbox.all()) {
      if (!wsClient.connected) break;
      const open = (item.body.dialog_id ?? null) === (store.dialogId ?? null);
      try {
        if (item.kind === "image") {
          const r = await wsClient.generateImage(
            item.body.message,
            item.body.dialog_id ?? null,
            () => {},
            item.id,
          );
          if (r.url) {
            imagesStore.prepend({
              id: Date.now(),
              url: r.url,
              prompt: item.body.message,
              dialog_id: r.dialog_id ?? item.body.dialog_id ?? "",
              created_at: new Date().toISOString(),
            });
          }
        } else {
          await wsClient.chatStream(item.body, undefined, item.id);
        }
        outbox.remove(item.id);
        if (open) touchedOpenDialog = true;
      } catch (e) {
        const m = e instanceof Error ? e.message : String(e);
        if (e instanceof LimitError) {
          // лимит исчерпан - не копим (иначе уйдёт устаревшим через час), показываем отсчёт
          startLimitCountdown(e.kind, e.retryAfter);
          outbox.remove(item.id);
          if (open) touchedOpenDialog = true;
          break;
        }
        if (m === "network error") break;
        if (m === "already generating") {
          // диалог занят - не теряем, повторим позже
          if (outbox.markAttempt(item.id) >= 8) {
            outbox.remove(item.id); // страховка от залипания
            if (open) touchedOpenDialog = true;
          }
          continue;
        }
        // терминальная ошибка - не зацикливаемся
        outbox.remove(item.id);
        if (open) touchedOpenDialog = true;
      }
    }
  } finally {
    flushingOutbox = false;
  }
  // заменяем «ожидающие» пузыри реальной историей
  if (touchedOpenDialog && wsClient.connected) {
    store.chatHistoryPrefetchOk = false;
    loadChatHistory();
  }
}

function injectPendingOutbox(): void {
  if (wsClient.connected) {
    flushOutbox();
    return;
  }
  const did = store.dialogId ?? null;
  let added = false;
  for (const item of outbox.all()) {
    if ((item.body.dialog_id ?? null) !== did) continue;
    chatMessages.value.push({
      type: "user",
      contentType: item.body.image_url ? "image" : "text",
      text: item.body.message,
      imageUrl: item.body.image_url ?? null,
      localUrl: item.localUrl ?? null,
    });
    chatMessages.value.push({ type: "bot", contentType: "text", text: "" });
    added = true;
  }
  if (added) {
    store.setChatHistory(chatMessages.value);
    nextTick().then(scrollToBottom);
  }
}

watch(initialLoadDone, (done) => {
  if (done) injectPendingOutbox();
});

// markdown-стек грузится отдельным чанком (обычно уже в AppLoading) - здесь подстраховка
preloadMarkdown();

function fallbackMd(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>");
}

function renderRaw(text: string): string {
  const r = renderMarkdownSafe(text);
  return r !== null ? r : fallbackMd(text);
}

// кэш готовых сообщений - formatMessage не пере-парсит статичные ответы на каждый рендер
const mdCache = new Map<string, string>();
function formatMessage(text: string): string {
  void markdownReady.value; // реактивная зависимость - перерисовка после загрузки чанка
  const hit = mdCache.get(text);
  if (hit !== undefined) return hit;
  const html = renderRaw(text);
  if (markdownReady.value) {
    mdCache.set(text, html);
    if (mdCache.size > 300) mdCache.delete(mdCache.keys().next().value as string);
  }
  return html;
}

// троттлинг рендера активного стрима - тяжёлый markdown не гоняется на каждый чанк
const STREAM_RENDER_MS = 70;
const streamHtml = ref("");
let streamRenderTs = 0;
let streamRenderTimer: ReturnType<typeof setTimeout> | null = null;

function renderStreamNow() {
  streamRenderTimer = null;
  streamRenderTs = Date.now();
  const i = streamingBotIdx.value;
  streamHtml.value = i >= 0 ? renderRaw(chatMessages.value[i]?.text ?? "") : "";
}

function bumpStreamRender() {
  const elapsed = Date.now() - streamRenderTs;
  if (elapsed >= STREAM_RENDER_MS) {
    renderStreamNow();
  } else if (!streamRenderTimer) {
    streamRenderTimer = setTimeout(renderStreamNow, STREAM_RENDER_MS - elapsed);
  }
}

function resetStreamRender() {
  if (streamRenderTimer) {
    clearTimeout(streamRenderTimer);
    streamRenderTimer = null;
  }
  streamRenderTs = 0;
  streamHtml.value = "";
}

function onContentClick(e: MouseEvent) {
  const target = e.target as HTMLElement;

  const link = target.closest("a[href]") as HTMLAnchorElement | null;
  if (link) {
    const href = link.getAttribute("href") || "";
    if (/^https?:\/\//i.test(href)) {
      e.preventDefault();
      try {
        openLink(href);
      } catch {
        window.open(href, "_blank", "noopener");
      }
    }
    return;
  }

  const btn = target.closest(".code-copy") as HTMLElement | null;
  if (!btn) return;
  const code = btn.closest(".code-block")?.querySelector("code");
  const text = code?.textContent ?? "";
  if (!text) return;
  writeClipboard(text).then((ok) => {
    if (!ok) return;
    btn.classList.add("code-copy--done");
    setTimeout(() => btn.classList.remove("code-copy--done"), 1500);
  });
}

function stripHtml(html: string): string {
  const el = document.createElement("div");
  el.innerHTML = html
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/pre>/gi, "\n")
    .replace(/<\/p>/gi, "\n")
    .replace(/<\/div>/gi, "\n");
  return (el.textContent ?? "").replace(/\n{3,}/g, "\n\n").trim();
}

function toggleMoreMenu(index: number, event: MouseEvent) {
  if (moreMenuIndex.value === index) {
    moreMenuIndex.value = null;
    return;
  }
  moreMenuIndex.value = index;
  const btn = event.currentTarget as HTMLElement;
  const rect = btn.getBoundingClientRect();
  const footerHeight = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue(
      "--footer-height",
    ) || "80",
  );
  const spaceBelow = window.innerHeight - rect.bottom - footerHeight;
  moreMenuUp.value = spaceBelow < 100;
}

function onReaction(index: number, reaction: "like" | "dislike") {
  if (reactionMap.get(index) === reaction) {
    reactionMap.delete(index); // toggle off - снять реакцию
    return;
  }
  reactionMap.set(index, reaction);
  api
    .sendReaction({
      reaction,
      model: currentModelId.value,
      dialog_id: store.dialogId,
      message_id: chatMessages.value[index]?.id,
    })
    .catch((err) => console.warn("[reaction]", err));
}

/**
 * Universal file save - cascade of 4 strategies:
 * 1. showSaveFilePicker  > native "Save As" dialog (Chromium desktop / tdesktop)
 * 2a. navigator.share({files}) > system share sheet (iOS, Android, macOS)
 *     – canShare() guard removed: it returns false on Android even when share works
 * 2b. navigator.share({text}) > text-only share fallback for TXT on Android
 * 3. window.open(_blank)  > opens blob in browser tab; escapes iframe sandbox (Telegram Web)
 * 4. a.download           > traditional auto-download (emergency fallback)
 */

// Minimal typings for the File System Access API (not in lib.dom.d.ts yet in all TS versions)
interface FsWritable {
  write(data: Blob): Promise<void>;
  close(): Promise<void>;
}
interface FsHandle {
  createWritable(): Promise<FsWritable>;
}
type ShowSaveFilePicker = (opts: {
  suggestedName?: string;
  types?: { description: string; accept: Record<string, string[]> }[];
}) => Promise<FsHandle>;

/**
 * Platform-aware universal file save.
 * Order for ALL platforms:
 *   1. showSaveFilePicker - native “Save As” dialog (Chromium: tdesktop, Chrome desktop)
 *   2. navigator.share({files}) - system share sheet (iOS, Android, macOS, Chrome Win/Mac)
 *   3. navigator.share({text}) - text-only fallback for TXT when file share is unavailable
 *   4. a.download - last resort (tdesktop fallback, some Android WebViews)
 *
 * window.open(blob) is intentionally NOT used - opens a raw blob URL in browser, which
 * is meaningless on macOS/Android and confusing everywhere else.
 * AbortError (user dismissed) always stops the cascade immediately.
 */
async function saveBlob(
  blob: Blob,
  filename: string,
  pickerTypes: { description: string; accept: Record<string, string[]> }[],
  /** Plain text - enables share({text}) fallback for TXT */
  plainText?: string,
): Promise<void> {
  // 1. Save As dialog (Chromium desktop, tdesktop)
  const filePicker = (
    window as Window & { showSaveFilePicker?: ShowSaveFilePicker }
  ).showSaveFilePicker;
  if (typeof filePicker === "function") {
    try {
      const handle = await filePicker({
        suggestedName: filename,
        types: pickerTypes,
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return;
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") return;
      // SecurityError (sandboxed iframe) or NotAllowedError (no gesture) - fall through
    }
  }

  // 2. Web Share API with files (iOS, Android, macOS, Chrome on Windows/macOS)
  // No canShare() guard - it returns false on some Android WebViews even when
  // navigator.share({files}) actually succeeds.
  if (typeof navigator.share === "function") {
    const file = new File([blob], filename, { type: blob.type });
    try {
      await navigator.share({ files: [file] });
      return;
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") return;
      // TypeError / NotAllowedError: file sharing not supported - try text
    }

    // 3. Text-only share - TXT fallback (Android when file share unavailable)
    if (plainText) {
      try {
        await navigator.share({ title: filename, text: plainText });
        return;
      } catch (err: unknown) {
        if ((err as Error)?.name === "AbortError") return;
      }
    }
  }

  // 4. a.download - last resort
  // Works in tdesktop (shows Downloads panel), some Android WebViews.
  // Blocked in sandboxed iframes (Telegram Web in browser) - acceptable
  // since those platforms should be handled by share API above.
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

function exportTxt(html: string) {
  moreMenuIndex.value = null;
  const text = stripHtml(html);
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  saveBlob(
    blob,
    "monkey-ai-response.txt",
    [{ description: "Text file", accept: { "text/plain": [".txt"] } }],
    text,
  ).catch((err) => console.error("[exportTxt]", err));
}

async function exportPdf(html: string) {
  moreMenuIndex.value = null;
  const text = stripHtml(html);

  // Render plain text via hidden div - all Unicode works, no HTML tags
  const el = document.createElement("div");
  el.style.cssText = [
    "position:fixed",
    "left:-9999px",
    "top:0",
    "width:620px",
    "padding:32px 40px",
    'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
    "font-size:14px",
    "line-height:1.75",
    "color:#111111",
    "background:#ffffff",
    "white-space:pre-wrap",
    "word-break:break-word",
  ].join(";");
  el.textContent = text;
  document.body.appendChild(el);

  try {
    const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
      import("html2canvas"),
      import("jspdf"),
    ]);

    const canvas = await html2canvas(el, {
      scale: 2,
      backgroundColor: "#ffffff",
      logging: false,
    });

    const pdf = new jsPDF({ unit: "mm", format: "a4" });
    const pw = pdf.internal.pageSize.getWidth();
    const ph = pdf.internal.pageSize.getHeight();
    const m = 14;
    const iw = pw - m * 2;
    const ih = (canvas.height / canvas.width) * iw;

    if (ih <= ph - m * 2) {
      pdf.addImage(canvas.toDataURL("image/png"), "PNG", m, m, iw, ih);
    } else {
      const pageHeightPx = Math.floor(((ph - m * 2) * canvas.width) / iw);
      let offsetPx = 0;
      while (offsetPx < canvas.height) {
        const sliceH = Math.min(pageHeightPx, canvas.height - offsetPx);
        const sliceCanvas = document.createElement("canvas");
        sliceCanvas.width = canvas.width;
        sliceCanvas.height = sliceH;
        sliceCanvas
          .getContext("2d")!
          .drawImage(
            canvas,
            0,
            offsetPx,
            canvas.width,
            sliceH,
            0,
            0,
            canvas.width,
            sliceH,
          );
        const sliceIh = (sliceH / canvas.width) * iw;
        pdf.addImage(
          sliceCanvas.toDataURL("image/png"),
          "PNG",
          m,
          m,
          iw,
          sliceIh,
        );
        offsetPx += sliceH;
        if (offsetPx < canvas.height) pdf.addPage();
      }
    }

    const pdfBlob = pdf.output("blob");
    await saveBlob(pdfBlob, "monkey-ai-response.pdf", [
      { description: "PDF document", accept: { "application/pdf": [".pdf"] } },
    ]);
  } catch (err) {
    console.error("[exportPdf]", err);
  } finally {
    if (document.body.contains(el)) document.body.removeChild(el);
  }
}

function legacyCopy(plain: string): boolean {
  const ta = document.createElement("textarea");
  ta.value = plain;
  ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(ta);
  window.getSelection()?.removeAllRanges();
  return ok;
}

function writeClipboard(plain: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard
      .writeText(plain)
      .then(() => true)
      .catch(() => legacyCopy(plain)); // iOS fallback
  }
  return Promise.resolve(legacyCopy(plain));
}

function copyToClipboard(text: string, index: number) {
  const plain = stripHtml(renderRaw(text));
  writeClipboard(plain).then((ok) => {
    window.getSelection()?.removeAllRanges();
    if (ok) {
      copiedIndex.value = index;
      if (copyTimeout) clearTimeout(copyTimeout);
      copyTimeout = setTimeout(() => {
        copiedIndex.value = null;
      }, 1200);
    } else {
      copiedIndex.value = null;
    }
  });
}

/* Случайная обезьянка для пустого чата */
const emptyCardImage = ref("");

let footerResizeObs: ResizeObserver | null = null;
/** Unsubscribe callbacks for Telegram viewport signal subscriptions. */
const viewportUnsub: Array<() => void> = [];

// iOS: touch-triggered tooltip - briefly shows tooltip on tap, then removes it
let tipActiveTimer: ReturnType<typeof setTimeout> | null = null;
function handleTipTouch(e: TouchEvent) {
  if (!document.body.classList.contains("ios-gpt")) return;
  const wrap = (e.target as Element).closest<HTMLElement>(
    ".btn-tip-wrap[data-tip]",
  );
  if (!wrap) return;
  // Clear previous active tip
  document
    .querySelectorAll<HTMLElement>(".tip-active")
    .forEach((el) => el.classList.remove("tip-active"));
  if (tipActiveTimer) clearTimeout(tipActiveTimer);
  wrap.classList.add("tip-active");
  // Remove after 700ms - enough to read, gone before next interaction
  tipActiveTimer = setTimeout(() => {
    wrap.classList.remove("tip-active");
    tipActiveTimer = null;
  }, 700);
}

function recomposeScrollLayer() {
  const node = chatContent.value;
  if (!node) return;
  const top = node.scrollTop;
  node.scrollTop = top > 0 ? top - 1 : 1;
  void node.offsetHeight; // flush the scroll change so the layer actually recomposes
  node.scrollTop = top;
  node.style.opacity = "0.999";
  void node.offsetHeight;
  node.style.opacity = "";
}

/** Run the recompose once the resume/expand settles (twice: next frame + short delay). */
function scheduleRecompose() {
  requestAnimationFrame(recomposeScrollLayer);
  setTimeout(recomposeScrollLayer, 250);
}

/** OS-level background>foreground (belt-and-suspenders alongside the viewport-expand hook). */
function handleResumeRepaint() {
  if (document.visibilityState !== "visible") return;
  scheduleRecompose();
}

onMounted(async () => {
  const images = [
    monkeyChemistry,
    monkeyHacker,
    monkeyHappy,
    monkeyIdea,
    monkeyQuestion,
    monkeyRead,
    monkeyShock,
    monkeyWork,
    monkeyWorkout,
  ];
  emptyCardImage.value = images[Math.floor(Math.random() * images.length)];

  // Track footer height for the scroll-to-bottom button positioning
  await nextTick();
  const footerEl = document.querySelector("footer");
  if (footerEl) {
    const updateFooterHeight = () => {
      // While MainPage is KeepAlive-deactivated (Settings open) the footer is detached.
      // getBoundingClientRect() then returns 0, which would set --footer-height: 0px,
      // collapse the .chat-end-spacer and shrink scrollHeight by ~footer-height. On return
      // the browser clamps the restored scrollTop to the (now lower) bottom - yanking the
      // user down and hiding the scroll button when they were within ~spacer-height of the
      // bottom. Skip the measurement until the footer is reattached.
      if (!footerEl.isConnected) return;
      const el = chatContent.value;
      // Check proximity to bottom BEFORE layout changes
      const atBottom = el
        ? el.scrollHeight - el.scrollTop - el.clientHeight < 4
        : false;
      document.documentElement.style.setProperty(
        "--footer-height",
        `${footerEl.getBoundingClientRect().height}px`,
      );
      // If user was at true bottom, keep them there after footer height change.
      // This prevents the 10px jump caused by padding-bottom increasing scrollHeight.
      if (atBottom && el) {
        requestAnimationFrame(() => {
          el.scrollTop = el.scrollHeight;
        });
      }
    };
    updateFooterHeight();
    footerResizeObs = new ResizeObserver(updateFooterHeight);
    footerResizeObs.observe(footerEl);

    // The ResizeObserver only fires when the footer ELEMENT resizes. The launch gap is
    // caused by the Telegram viewport / bottom safe-area settling AFTER mount, which does
    // not resize the footer - so the layout used to fix itself only "over time". Recompute
    // as soon as the stable height or bottom inset actually changes.
    try {
      viewportUnsub.push(viewport.stableHeight.sub(updateFooterHeight));
      viewportUnsub.push(viewport.safeAreaInsetBottom.sub(updateFooterHeight));
      // Reopened from the Telegram dock > the viewport expands (isExpanded flips to true).
      // This is the reliable signal for dock-reopen (visibilitychange may not fire), so
      // recompose the scroll layer here to kill the stale-snapshot overlap.
      viewportUnsub.push(
        viewport.isExpanded.sub(() => {
          let expanded = true;
          try {
            expanded = (viewport.isExpanded as unknown as () => boolean)();
          } catch {
            expanded = true;
          }
          if (expanded) scheduleRecompose();
        }),
      );
    } catch {
      // Non-TMA / desktop mock env - viewport signals unavailable; ignore.
    }
  }

  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("touchstart", handleTipTouch, { passive: true });
  document.addEventListener("visibilitychange", handleResumeRepaint);

  // Proactively open WebSocket so the first message feels instant.
  wsClient.connect().catch(() => {});

  // Multi-device sync: type handlers
  // These fire when a broadcast arrives from ANOTHER device (no matching id-handler).

  // Another device sent a user message > add it + an empty bot slot.
  wsClient.setTypeHandler("user_message", (msg) => {
    // только если это сообщение из открытого сейчас диалога (иначе чужой чат)
    if ((msg.dialog_id ?? null) !== (store.dialogId ?? null)) return;
    const text = (msg.text as string) ?? "";
    const imageUrl = (msg.image_url as string) ?? null;
    if (!text && !imageUrl) return;
    // Ensure prior history is visible before appending the new stream slot.
    if (!chatMessages.value.length && store.chatHistory.length) {
      chatMessages.value = [...store.chatHistory];
    }
    chatMessages.value.push({
      text,
      type: "user",
      contentType: imageUrl ? "image" : "text",
      imageUrl,
      imageW: (msg.image_w as number) ?? null,
      imageH: (msg.image_h as number) ?? null,
    });
    chatMessages.value.push({ type: "bot", contentType: "text", text: "" });
    const botIdx = chatMessages.value.length - 1;
    remoteBotSlots.set(msg.id as string, botIdx);
    resetStreamRender();
    streamingBotIdx.value = botIdx;
    nextTick().then(scrollToBottomIfAtBottom);
  });

  // Generation is starting on another device > show loading state.
  wsClient.setTypeHandler("generation_start", (msg) => {
    const botIdx = remoteBotSlots.get(msg.id as string);
    if (botIdx !== undefined) {
      // Slot was created by user_message handler - just ensure streaming is marked.
      streamingBotIdx.value = botIdx;
    }
  });

  // Стрим-дельта генерации с другого устройства - живой текст в слоте.
  wsClient.setTypeHandler("chat_delta", (msg) => {
    const botIdx = remoteBotSlots.get(msg.id as string);
    if (botIdx === undefined) return;
    const text = (msg.text as string) ?? "";
    if (!text) return;
    chatMessages.value[botIdx] = { type: "bot", contentType: "text", text };
    bumpStreamRender();
    nextTick().then(scrollToBottomIfAtBottom);
  });

  // Another device's chat finished.
  wsClient.setTypeHandler("chat_done", (msg) => {
    const id = msg.id as string;
    const botIdx = remoteBotSlots.get(id);
    if (botIdx === undefined) return; // не наш слот / чужой диалог
    remoteBotSlots.delete(id);
    streamingBotIdx.value = -1;
    const isFlagged = (msg.is_flagged as boolean) ?? false;
    const m = (msg.message ?? null) as { id?: string; content?: string } | null;
    chatMessages.value[botIdx] = {
      type: "bot",
      contentType: "text",
      text: isFlagged ? t("message_flagged") : (m?.content ?? ""),
      id: m?.id,
    };
    if (msg.dialog_id) store.setDialogId(msg.dialog_id as string);
    store.setChatHistory(chatMessages.value);
    nextTick().then(scrollToBottomIfAtBottom);
  });

  // Another device's chat errored.
  wsClient.setTypeHandler("chat_error", (msg) => {
    const id = msg.id as string;
    const botIdx = remoteBotSlots.get(id);
    if (botIdx === undefined) return;
    remoteBotSlots.delete(id);
    streamingBotIdx.value = -1;
    chatMessages.value[botIdx] = {
      type: "bot",
      contentType: "text",
      text:
        t("error_response") + ": " + ((msg.error as string) || "chat error"),
    };
    store.setChatHistory(chatMessages.value);
  });

  // Another device's image progress - keep spinner (no text change).
  wsClient.setTypeHandler("image_progress", () => {});

  // Another device's image finished.
  wsClient.setTypeHandler("image_done", (msg) => {
    const id = msg.id as string;
    const botIdx = remoteBotSlots.get(id);
    if (botIdx === undefined) return;
    remoteBotSlots.delete(id);
    streamingBotIdx.value = -1;
    const rawUrl = (msg.url as string) ?? "";
    const imageUrl = rawUrl.startsWith("/") ? `${BASE_URL}${rawUrl}` : rawUrl;
    chatMessages.value[botIdx] = {
      type: "bot",
      contentType: "image",
      imageUrl,
      text: "",
      id: (msg.message as { id?: string } | undefined)?.id,
    };
    if (msg.dialog_id) store.setDialogId(msg.dialog_id as string);
    store.setChatHistory(chatMessages.value);
    nextTick().then(scrollToBottomIfAtBottom);
  });

  // Another device's image errored.
  wsClient.setTypeHandler("image_error", (msg) => {
    const id = msg.id as string;
    const botIdx = remoteBotSlots.get(id);
    if (botIdx === undefined) return;
    remoteBotSlots.delete(id);
    streamingBotIdx.value = -1;
    chatMessages.value[botIdx] = {
      type: "bot",
      contentType: "text",
      text:
        t("error_response") + ": " + ((msg.error as string) || "image error"),
    };
    store.setChatHistory(chatMessages.value);
  });

  // Connection lost (WebSocket closed) - reset streaming state.
  wsClient.setTypeHandler("connection_lost", () => {
    remoteBotSlots.clear();
    streamingBotIdx.value = -1;
  });

  // Connected while a generation is already running on another device.
  // Push the original user message + empty bot slot so the spinner shows
  // and incoming chat_delta / image_progress frames have somewhere to land.
  wsClient.setTypeHandler("connection_ack", async (msg) => {
    flushOutbox();
    const genId = msg.generating_id as string | undefined;
    if (msg.is_generating) {
      if (genId && genId === pendingReconnectReqId.value) {
        // Our own image generation survived the disconnect - restore the spinner slot.
        remoteBotSlots.set(genId, pendingReconnectBotIdx.value);
        streamingBotIdx.value = pendingReconnectBotIdx.value;
        pendingReconnectReqId.value = null;
        pendingReconnectBotIdx.value = -1;
      } else if (streamingBotIdx.value === -1) {
        // Another device's generation - check for an existing slot first.
        // user_message handler may have already added the pair before a WS disconnect;
        // connection_lost clears remoteBotSlots but chatMessages is still intact.
        const text = (msg.generating_text as string) ?? "";
        const n = chatMessages.value.length;
        const existingSlot =
          n >= 2 &&
          chatMessages.value[n - 1]?.type === "bot" &&
          chatMessages.value[n - 1]?.text === "" &&
          (!text || chatMessages.value[n - 2]?.text === text);

        if (existingSlot) {
          // Reuse the existing bot slot - just restore streaming state.
          if (genId) remoteBotSlots.set(genId, n - 1);
          streamingBotIdx.value = n - 1;
        } else {
          // First time seeing this generation - show prior history, then add slot.
          if (!chatMessages.value.length && store.chatHistory.length) {
            chatMessages.value = [...store.chatHistory];
          }
          if (text) chatMessages.value.push({ text, type: "user" });
          chatMessages.value.push({
            type: "bot",
            contentType: "text",
            text: "",
          });
          const botIdx = chatMessages.value.length - 1;
          if (genId) remoteBotSlots.set(genId, botIdx);
          streamingBotIdx.value = botIdx;
          nextTick().then(scrollToBottomIfAtBottom);
        }
      }
    } else if (pendingReconnectReqId.value) {
      // Server says nothing is generating, but we were waiting for an image.
      // Two outcomes are possible:
      //   A) Image was generated and saved to DB while WS was down > show from history.
      //   B) Generation failed / never reached server > auto-retry the request.
      const savedBotIdx = pendingReconnectBotIdx.value;
      // Capture the user's original prompt before clearing state (needed for retry).
      const savedText =
        savedBotIdx > 0 && savedBotIdx < chatMessages.value.length
          ? (chatMessages.value[savedBotIdx - 1]?.text ?? "")
          : "";
      pendingReconnectReqId.value = null;
      pendingReconnectBotIdx.value = -1;
      streamingBotIdx.value = -1;
      // Replace the spinner slot with an empty slot while we fetch (CSS spinner).
      if (savedBotIdx >= 0 && savedBotIdx < chatMessages.value.length) {
        chatMessages.value[savedBotIdx] = {
          type: "bot",
          contentType: "text",
          text: "",
        };
      }
      store.chatHistoryPrefetchOk = false;
      try {
        const { dialog_id, messages, next_before_index } =
          await api.bootstrapDialog();
        store.setDialogId(dialog_id);
        const freshHistory = dialogMessagesToChat(messages ?? []);
        if (hasLoadedOlderPages.value) {
          // User had loaded older messages - preserve them.
          // Keep the head of chatMessages that extends beyond the bootstrap window,
          // then replace the tail with fresh data (which contains the new exchange).
          const olderCount = Math.max(
            0,
            chatMessages.value.length - freshHistory.length,
          );
          const merged = [
            ...chatMessages.value.slice(0, olderCount),
            ...freshHistory,
          ];
          applyChatHistory(merged);
          // cursorIdx stays as-is; hasMoreToLoad stays as-is (user already loaded what they wanted).
        } else {
          applyChatHistory(freshHistory);
          cursorIdx.value = next_before_index;
          hasMoreToLoad.value = next_before_index > 0;
        }
        await nextTick();
        scrollToBottom();
        // Check whether the response arrived in DB while WS was down.
        const responseArrived = savedText
          ? freshHistory.some((m, i) => {
              if (m.type === "user" && m.text === savedText) {
                const next = freshHistory[i + 1];
                return pendingReconnectIsImage.value
                  ? next?.contentType === "image"
                  : next?.contentType === "text" && !!next?.text;
              }
              return false;
            })
          : true; // no prompt captured > don't retry
        if (!responseArrived && savedText) {
          // Generation was lost (not in DB) - re-submit the request automatically.
          messageText.value = savedText;
          if (editableDiv.value) editableDiv.value.innerText = savedText;
          sendMessage();
        }
      } catch {
        // Network error during bootstrap - use loadChatHistory WITHOUT forceScroll so
        // hasLoadedOlderPages guard is respected (older messages are preserved).
        loadChatHistory();
      }
    } else if (initialLoadDone.value) {
      // Reconnected while idle - refresh history to pick up messages from other devices.
      store.chatHistoryPrefetchOk = false;
      loadChatHistory();
    }
  });

  const routeDialogId = route.params.dialogId;
  if (routeDialogId === "new") {
    openDraftChat();
    initialLoadDone.value = true;
    return;
  }
  if (typeof routeDialogId === "string" && routeDialogId) {
    // префетч уже загрузил этот же диалог - НЕ перезагружаем (без мерцания фото/двойной загрузки)
    if (store.chatHistoryPrefetchOk && store.dialogId === routeDialogId) {
      applyChatHistory([...store.chatHistory]);
      cursorIdx.value = store.chatHistoryNextCursor;
      hasMoreToLoad.value = store.chatHistoryNextCursor > 0;
      await nextTick();
      jumpToBottomSilent();
    } else {
      await loadDialogById(routeDialogId);
    }
    initialLoadDone.value = true;
    maybeAutoGenerate();
    return;
  }

  if (store.chatHistoryPrefetchOk) {
    await loadChatHistory(true);
    initialLoadDone.value = true;
    return;
  }

  await loadChatHistory(true);
  initialLoadDone.value = true;
  // scrollToBottom is now handled inside loadChatHistory based on position.
});

// Switching between dialogs from Recents while ChatPage stays mounted (KeepAlive).
watch(
  () => route.params.dialogId,
  (id) => {
    if (id === "new") {
      // повторное «новый чат» из активного диалога - чистый черновик
      if (store.dialogId !== null || chatMessages.value.length) openDraftChat();
      return;
    }
    if (typeof id === "string" && id && id !== store.dialogId) {
      loadDialogById(id).then(() => maybeAutoGenerate());
    }
  },
);

let wasOnChat = false;

onActivated(() => {
  if (!wasOnChat) return;
  // Snapshot the target now - onChatScroll could overwrite savedScrollTop mid-restore.
  const target = savedScrollTop;
  isReturningFromSettings.value = true;
  const restore = () => {
    const el = chatContent.value;
    if (!el) return;
    suppressScrollEvents = true;
    // null = user never scrolled this session > land at the bottom.
    el.scrollTop = target ?? el.scrollHeight;
    suppressScrollEvents = false;
  };
  nextTick(() => {
    restore();
    // Re-apply after reattach paint: KeepAlive can reset scrollTop to 0 post-restore.
    requestAnimationFrame(() => {
      restore();
      // Recalculate scroll state directly - onChatScroll's hysteresis would leave
      // showScrollBtn=false (set by onDeactivated) when restoring into the 60–120px zone.
      const el = chatContent.value;
      if (el) {
        const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
        isNearBottom.value = dist < 150;
        showScrollBtn.value = dist > 60;
        savedScrollTop = el.scrollTop;
      }
      isReturningFromSettings.value = false;
    });
  });
});

onDeactivated(() => {
  wasOnChat = true;
  // NOTE: do NOT read scrollTop here - KeepAlive has already detached the DOM and
  // reset it to 0. The real position is captured live in onChatScroll (savedScrollTop).
  // Hide cached scroll button before KeepAlive stores the inactive DOM snapshot.
  showScrollBtn.value = false;
  isReturningFromSettings.value = true;
  // Cancel any in-flight smooth scroll so onChatScroll correctly updates the button on return.
  if (smoothScrollWatchdog !== null) {
    clearTimeout(smoothScrollWatchdog);
    smoothScrollWatchdog = null;
  }
  smoothScrollActive = false;
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleDocumentClick);
  document.removeEventListener("touchstart", handleTipTouch);
  document.removeEventListener("visibilitychange", handleResumeRepaint);
  if (tipActiveTimer) clearTimeout(tipActiveTimer);
  document.body.style.overflow = "auto";
  if (copyTimeout) clearTimeout(copyTimeout);
  if (limitTimer) { clearInterval(limitTimer); limitTimer = null; }
  if (smoothScrollWatchdog !== null) clearTimeout(smoothScrollWatchdog);
  if (composerMirror) { composerMirror.remove(); composerMirror = null; }
  footerResizeObs?.disconnect();
  for (const unsub of viewportUnsub) unsub();
  viewportUnsub.length = 0;
  // Remove type handlers so they don't fire after the component is gone.
  for (const type of [
    "user_message",
    "generation_start",
    "chat_delta",
    "chat_done",
    "chat_error",
    "image_progress",
    "image_done",
    "image_error",
    "connection_lost",
    "connection_ack",
  ]) {
    wsClient.setTypeHandler(type, null);
  }
});
</script>

<style>
/* Базовые стили */
.image-container {
  margin: 8px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

/* Load more button */
.load-more-row {
  display: flex;
  justify-content: center;
  padding: 10px 16px 6px;
}

.load-more-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 22px;
  border: none;
  border-radius: 10px;
  background: var(--tg-theme-button-color, #3390ec);
  color: var(--tg-theme-button-text-color, #fff);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.18s ease;
  user-select: none;
}

.load-more-btn:hover:not(:disabled) {
  opacity: 0.85;
}

.load-more-btn:active:not(:disabled) {
  opacity: 0.7;
}

.load-more-btn--loading,
.load-more-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.load-more-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: lm-spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes lm-spin {
  to {
    transform: rotate(360deg);
  }
}

/* Hide img tag while skeleton is visible to avoid flash of broken icon */
.image-loading {
  display: none;
}

.generated-image {
  width: 240px;
  height: 240px;
  border-radius: 8px;
  object-fit: cover;
  cursor: pointer;
  transition: transform 0.2s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.generated-image:hover {
  transform: scale(1.02);
}

/* Модальное окно для просмотра изображений */
.image-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.85);
  z-index: 1000;
  display: flex;
  justify-content: center;
  align-items: center;
}

.image-modal img {
  max-width: 90%;
  max-height: 90%;
  object-fit: contain;
  border-radius: 4px;
}

/* Композер (адаптив ChatGPT: инлайн > многострочие переносит кнопки вниз) */
/* убираем нижнюю «полку» - кнопки живут в grid */
footer .footer__input .input__text {
  padding-bottom: 0;
}

/* инлайн: [+] · текст · [↑]. minmax(0,1fr) - иначе длинный текст растягивает трек и не переносится */
.composer-row {
  display: grid;
  grid-template-areas: "plus text send";
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  column-gap: 4px;
  padding: 5px;
}

/* многострочие: текст во всю ширину сверху, кнопки снизу */
.composer--stacked .composer-row {
  grid-template-areas:
    "text text text"
    "plus . send";
  row-gap: 2px;
  align-items: end;
}

.composer-text {
  grid-area: text;
  position: relative;
  min-width: 0;
}

/* «+» - плоская svg, статична в grid; специфичность выше footer .footer__input button{display:none} */
footer .footer__input .input__attach {
  grid-area: plus;
  position: static;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--icons-storke-color);
  cursor: pointer;
  overflow: hidden;
  transition: color 0.1s ease, opacity 0.1s ease;
}

footer .footer__input .input__attach.disabled {
  opacity: 0.4;
  cursor: default;
  pointer-events: none;
}

/* «отправить» - статична в grid справа (перебиваем глобальный absolute) */
footer .footer__input .input__submit {
  grid-area: send;
  position: static;
  justify-self: end;
}

/* плейсхолдер - в потоке текстовой зоны, не перекрывает превью */
footer .input__text .input__text-placeholder {
  top: 8px;
  left: 8px;
}

/* off-screen инпут - не display:none/hidden, иначе iOS не открывает пикер */
.composer-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  border: 0;
  opacity: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  pointer-events: none;
}

.attach-panel {
  position: absolute;
  left: 10px;
  bottom: calc(100% + 6px);
  min-width: 184px;
  padding: 6px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--second-bg-color);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.18);
  z-index: 300;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.attach-panel-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-color);
  font-size: 15px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
}

.attach-panel-item svg {
  color: var(--icons-storke-color);
  flex-shrink: 0;
}

.attach-panel-enter-active,
.attach-panel-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.attach-panel-enter-from,
.attach-panel-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.attach-preview {
  padding: 6px 8px 0 8px;
  display: flex;
}

.attach-thumb-wrap {
  position: relative;
  width: 44px;
  height: 44px;
}

.attach-thumb {
  width: 44px;
  height: 44px;
  object-fit: cover;
  border-radius: 10px;
  display: block;
  transition: filter 0.2s ease;
}

.attach-thumb-wrap.is-loading .attach-thumb {
  filter: blur(2px);
}

.attach-progress {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.12);
  border-radius: 10px;
}

.attach-ring {
  width: 24px;
  height: 24px;
  transform: rotate(-90deg);
}

.attach-ring-bg {
  fill: none;
  stroke: rgba(255, 255, 255, 0.3);
  stroke-width: 4;
}

.attach-ring-fg {
  fill: none;
  stroke: #fff;
  stroke-width: 4;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.15s linear;
}

.attach-failed {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: rgba(214, 48, 49, 0.55);
  color: #fff;
  font-weight: 700;
}

.attach-thumb-wrap .input__text-image-delete {
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  background-color: #fff;
  border: none;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
}

.attach-thumb-wrap .input__text-image-delete svg {
  fill: #1c1c1c;
}

/* группа сообщения: фото + пузырь рядом (gap 4px), между группами - gap чата (18px) */
.msg-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.msg-group--user {
  align-items: flex-end;
}

.msg-group--bot {
  align-items: flex-start;
}

/* фото пользователя в ленте - целиком, без пузыря, над текстом */
.user-photo {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
}

.user-photo--sized {
  max-width: 80%;
}

.user-photo-img {
  display: block;
  max-width: 300px;
  max-height: 380px;
  width: auto;
  height: auto;
  object-fit: contain;
  cursor: pointer;
}

/* размеры известны > бокс фиксирован, картинка заполняет 1:1 (аспект совпадает - без кропа) */
.user-photo--sized .user-photo-img {
  width: 100%;
  height: 100%;
  max-width: none;
  max-height: none;
  object-fit: cover;
}

.user-photo-skeleton {
  position: absolute;
  inset: 0;
  background: #e5e5ea;
}

body.dark .user-photo-skeleton {
  background: #3a3a3c;
}


.scroll-to-bottom-btn {
  position: fixed;
  right: 16px;
  bottom: calc(var(--footer-height, 80px) + 12px);
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: none;
  background: var(--third-bg-color, #3d3d3f);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 50;
  padding: 0;
  transition: background-color 0.15s ease;
  /* Force own GPU compositing layer so border-radius is applied from the very
     first frame - prevents the brief "square" rendering artifact on Android. */
  transform: translateZ(0);
}

/* Dark theme: lighten slightly on hover */
.scroll-to-bottom-btn:hover {
  background-color: color-mix(
    in srgb,
    var(--third-bg-color, #3d3d3f) 80%,
    #fff 20%
  );
}

/* Light theme: darken slightly on hover */
body:not(.dark) .scroll-to-bottom-btn:hover {
  background-color: color-mix(in srgb, var(--third-bg-color) 75%, #000 25%);
}

.scroll-btn-fade-enter-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.scroll-btn-fade-leave-active {
  transition: none;
}

.scroll-btn-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

/* Bottom spacer - replaces padding-bottom on .chat-content.
   Fixes iOS Safari flex+overflow not scrolling into CSS padding area. */
.chat-end-spacer {
  flex-shrink: 0;
  min-height: calc(var(--footer-height, 80px) + 16px);
  pointer-events: none;
}

/* Hide chat for a moment during Settings->Chat restore to prevent stale-frame flicker.
   Visibility keeps layout metrics intact, unlike display:none. */
.chat-content--restoring {
  visibility: hidden;
}

.empty-card-img {
  pointer-events: none;
  -webkit-user-drag: none;
}
</style>