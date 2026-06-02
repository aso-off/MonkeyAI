<template>
  <div class="flex">
    <!-- Sidebar -->
    <div
      id="sidebar"
      :class="[
        'sidebar__wrapper',
        { 'sidebar__wrapper-active': sidebarActive },
      ]"
      :style="{ display: sidebarDisplay ? 'flex' : 'none' }"
      style="justify-content: space-between; position: fixed"
      @click="toggleSidebar"
    >
      <div class="sidebar">
        <div class="sidebar__user">
          <div class="sidebar__user-avatar">
            <img :src="model_logo" alt="" />
          </div>
          <div class="sidebar__user-container">
            <div class="sidebar__user-name">Monkey AI</div>
            <div class="sidebar__user-subscribe"></div>
          </div>
        </div>
        <div class="sidebar__nav">
          <!-- Кнопка очистки чата -->
          <button class="sidebar__item" @click="clearCurrentChat">
            <div class="sidebar__item-icon">
              <!-- Инлайн SVG для new_chat -->
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M8 12H12M12 12H16M12 12V16M12 12V8M12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12C21 16.9706 16.9706 21 12 21Z"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                ></path>
              </svg>
            </div>
            <div class="sidebar__item-text">{{ $t("new_chat") }}</div>
          </button>
          <button class="sidebar__item" @click="router.push('/settings')">
            <div class="sidebar__item-icon">
              <!-- Инлайн SVG для settings -->
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M20.3499 8.92293L19.9837 8.7192C19.9269 8.68756 19.8989 8.67169 19.8714 8.65524C19.5983 8.49165 19.3682 8.26563 19.2002 7.99523C19.1833 7.96802 19.1674 7.93949 19.1348 7.88309C19.1023 7.82677 19.0858 7.79823 19.0706 7.76998C18.92 7.48866 18.8385 7.17515 18.8336 6.85606C18.8331 6.82398 18.8332 6.79121 18.8343 6.72604L18.8415 6.30078C18.8529 5.62025 18.8587 5.27893 18.763 4.97262C18.6781 4.70053 18.536 4.44993 18.3462 4.23725C18.1317 3.99685 17.8347 3.82534 17.2402 3.48276L16.7464 3.1982C16.1536 2.85658 15.8571 2.68571 15.5423 2.62057C15.2639 2.56294 14.9765 2.56561 14.6991 2.62789C14.3859 2.69819 14.0931 2.87351 13.5079 3.22396L13.5045 3.22555L13.1507 3.43741C13.0948 3.47091 13.0665 3.48779 13.0384 3.50338C12.7601 3.6581 12.4495 3.74365 12.1312 3.75387C12.0992 3.7549 12.0665 3.7549 12.0013 3.7549C11.9365 3.7549 11.9024 3.7549 11.8704 3.75387C11.5515 3.74361 11.2402 3.65759 10.9615 3.50223C10.9334 3.48658 10.9056 3.46956 10.8496 3.4359L10.4935 3.22213C9.90422 2.86836 9.60915 2.69121 9.29427 2.62057C9.0157 2.55807 8.72737 2.55634 8.44791 2.61471C8.13236 2.68062 7.83577 2.85276 7.24258 3.19703L7.23994 3.1982L6.75228 3.48124L6.74688 3.48454C6.15904 3.82572 5.86441 3.99672 5.6517 4.23614C5.46294 4.4486 5.32185 4.69881 5.2374 4.97018C5.14194 5.27691 5.14703 5.61896 5.15853 6.3027L5.16568 6.72736C5.16676 6.79166 5.16864 6.82362 5.16817 6.85525C5.16343 7.17499 5.08086 7.48914 4.92974 7.77096C4.9148 7.79883 4.8987 7.8267 4.86654 7.88237C4.83436 7.93808 4.81877 7.96579 4.80209 7.99267C4.63336 8.26452 4.40214 8.49186 4.12733 8.65572C4.10015 8.67193 4.0715 8.68752 4.01521 8.71871L3.65365 8.91908C3.05208 9.25245 2.75137 9.41928 2.53256 9.65669C2.33898 9.86672 2.19275 10.1158 2.10349 10.3872C2.00259 10.6939 2.00267 11.0378 2.00424 11.7255L2.00551 12.2877C2.00706 12.9708 2.00919 13.3122 2.11032 13.6168C2.19979 13.8863 2.34495 14.134 2.53744 14.3427C2.75502 14.5787 3.05274 14.7445 3.64974 15.0766L4.00808 15.276C4.06907 15.3099 4.09976 15.3266 4.12917 15.3444C4.40148 15.5083 4.63089 15.735 4.79818 16.0053C4.81625 16.0345 4.8336 16.0648 4.8683 16.1255C4.90256 16.1853 4.92009 16.2152 4.93594 16.2452C5.08261 16.5229 5.16114 16.8315 5.16649 17.1455C5.16707 17.1794 5.16658 17.2137 5.16541 17.2827L5.15853 17.6902C5.14695 18.3763 5.1419 18.7197 5.23792 19.0273C5.32287 19.2994 5.46484 19.55 5.65463 19.7627C5.86915 20.0031 6.16655 20.1745 6.76107 20.517L7.25478 20.8015C7.84763 21.1432 8.14395 21.3138 8.45869 21.379C8.73714 21.4366 9.02464 21.4344 9.30209 21.3721C9.61567 21.3017 9.90948 21.1258 10.4964 20.7743L10.8502 20.5625C10.9062 20.5289 10.9346 20.5121 10.9626 20.4965C11.2409 20.3418 11.5512 20.2558 11.8695 20.2456C11.9015 20.2446 11.9342 20.2446 11.9994 20.2446C12.0648 20.2446 12.0974 20.2446 12.1295 20.2456C12.4484 20.2559 12.7607 20.3422 13.0394 20.4975C13.0639 20.5112 13.0885 20.526 13.1316 20.5519L13.5078 20.7777C14.0971 21.1315 14.3916 21.3081 14.7065 21.3788C14.985 21.4413 15.2736 21.4438 15.5531 21.3855C15.8685 21.3196 16.1657 21.1471 16.7586 20.803L17.2536 20.5157C17.8418 20.1743 18.1367 20.0031 18.3495 19.7636C18.5383 19.5512 18.6796 19.3011 18.764 19.0297C18.8588 18.7252 18.8531 18.3858 18.8417 17.7119L18.8343 17.2724C18.8332 17.2081 18.8331 17.1761 18.8336 17.1445C18.8383 16.8247 18.9195 16.5104 19.0706 16.2286C19.0856 16.2007 19.1018 16.1726 19.1338 16.1171C19.166 16.0615 19.1827 16.0337 19.1994 16.0068C19.3681 15.7349 19.5995 15.5074 19.8744 15.3435C19.9012 15.3275 19.9289 15.3122 19.9838 15.2818L19.9857 15.2809L20.3472 15.0805C20.9488 14.7472 21.2501 14.5801 21.4689 14.3427C21.6625 14.1327 21.8085 13.8839 21.8978 13.6126C21.9981 13.3077 21.9973 12.9658 21.9958 12.2861L21.9945 11.7119C21.9929 11.0287 21.9921 10.6874 21.891 10.3828C21.8015 10.1133 21.6555 9.86561 21.463 9.65685C21.2457 9.42111 20.9475 9.25525 20.3517 8.92378L20.3499 8.92293Z"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                ></path>
                <path
                  d="M8.00033 12C8.00033 14.2091 9.79119 16 12.0003 16C14.2095 16 16.0003 14.2091 16.0003 12C16.0003 9.79082 14.2095 7.99996 12.0003 7.99996C9.79119 7.99996 8.00033 9.79082 8.00033 12Z"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                ></path>
              </svg>
            </div>
            <div class="sidebar__item-text">{{ $t("settings") }}</div>
          </button>
        </div>
      </div>
      <div class="sidebar__close-wrapper">
        <button class="sidebar__close" @click="toggleSidebar">
          <!-- Инлайн SVG для close -->
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M18 6L6 18"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              d="M6 6L18 18"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>

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
              v-if="['gpt-5-nano', 'gpt-4o', 'gpt-5-mini'].includes(model.id)"
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
      <div class="header__sidebar" @click="toggleSidebar">
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
          >
            <path
              d="M16 10L12 14L8 10"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            ></path>
            <!-- Изменено stroke на currentColor -->
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
        <div v-if="hasMoreToLoad" class="load-more-row">
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
        <!-- Если сообщений ещё нет, показ пустой карточки -->
        <template v-if="chatMessages.length === 0">
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
              <img :src="emptyCardImage" alt="Пустой чат" />
            </div>
          </div>
        </template>
        <!-- Иначе вывод списка сообщений -->
        <template v-else>
          <div
            v-for="(msg, index) in chatMessages"
            :key="index"
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
                  <!-- Skeleton shimmer while the browser fetches the WebP -->
                  <div
                    v-if="msg.imageUrl && !loadedImages.has(msg.imageUrl)"
                    class="image-skeleton"
                  ></div>
                  <img
                    v-if="msg.imageUrl"
                    :src="msg.imageUrl"
                    alt=""
                    class="generated-image"
                    :class="{
                      'image-loading': !loadedImages.has(msg.imageUrl ?? ''),
                    }"
                    @load="loadedImages.add(msg.imageUrl!)"
                    @error="loadedImages.add(msg.imageUrl!)"
                    @click="openFullImage(msg.imageUrl ?? '')"
                  />
                </div>
              </div>

              <!-- Для текста -->
              <div v-else-if="msg.type === 'bot'">
                <!-- Лоадер: три пульсирующие точки пока AI ещё не начал отвечать -->
                <div
                  v-if="index === streamingBotIdx && !msg.text"
                  class="ai-thinking"
                >
                  <span></span><span></span><span></span>
                </div>
                <!-- Текст ответа -->
                <div v-if="msg.text" v-html="formatMessage(msg.text)"></div>
                <!-- Кнопки: копировать / лайк / дизлайк / три точки — только когда генерация завершена -->
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
                      @click="
                        onReaction(
                          index,
                          'like',
                          chatMessages[index - 1]?.text ?? '',
                          msg.text,
                        )
                      "
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
                      @click="
                        onReaction(
                          index,
                          'dislike',
                          chatMessages[index - 1]?.text ?? '',
                          msg.text,
                        )
                      "
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
                  <!-- Три точки (экспорт) — только для ios/macos/tdesktop -->
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
        </template>
        <!-- Spacer: replaces padding-bottom — fixes iOS Safari not including padding in scrollHeight -->
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
      <form class="footer__input" @submit.prevent="sendMessage">
        <div class="input__text null">
          <div
            id="editable-message-text"
            contenteditable="true"
            role="textbox"
            dir="ltr"
            ref="editableDiv"
            @input="onInput"
            @paste.prevent="onPaste"
          ></div>
          <span
            v-if="messageText.trim() === ''"
            class="input__text-placeholder"
          >
            {{ inputPlaceholder }}
          </span>
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
import { useRouter } from "vue-router";
import { retrieveLaunchParams } from "@tma.js/sdk-vue";
import { api, wsClient, BASE_URL } from "@/services/api";
import {
  useUserStore,
  dialogMessagesToChat,
  type ChatMessage,
} from "@/store/user";

defineOptions({ name: "MainPage" });

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
import model_logo from "@/components/img/model_logo.svg";

interface ModelOption {
  id: string;
  name: string;
  description: string;
}

const { t } = useI18n();
const router = useRouter();
const store = useUserStore();

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
/** True while a bootstrapDialog fetch is in-flight — prevents concurrent duplicate calls. */
let isLoadingHistory = false;
let copyTimeout: ReturnType<typeof setTimeout> | null = null;
let suppressScrollEvents = false;

/** True when the chat scroll is near the bottom (< 150px). Auto-scroll is only done here. */
const isNearBottom = ref(true);
/** True when user scrolled more than 100px from bottom — shows the scroll-to-bottom button. */
const showScrollBtn = ref(false);
/** True during first frame after returning from Settings to prevent stale button flash. */
const isReturningFromSettings = ref(false);
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

/* === Просмотр изображений === */
const fullImageUrl = ref("");
const showFullImage = ref(false);
// Tracks which image URLs have finished loading — used to show/hide skeleton.
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

/* === Сайдбар === */
const sidebarActive = ref(false);
const sidebarDisplay = ref(false);

function toggleSidebar() {
  if (sidebarActive.value) {
    sidebarActive.value = false;
    setTimeout(() => {
      sidebarDisplay.value = false;
    }, 200);
  } else {
    sidebarDisplay.value = true;
    setTimeout(() => {
      sidebarActive.value = true;
    }, 10);
  }
}

/* === Выбор модели === */
const models = computed<ModelOption[]>(() => [
  {
    id: "gpt-5-nano",
    name: "GPT 5 <span>Nano</span>",
    description: t("for_everyday_tasks"),
  },
  {
    id: "gpt-4o",
    name: "GPT 4 <span>Omni</span>",
    description: t("for_complex_tasks"),
  },
  {
    id: "gpt-5-mini",
    name: "GPT 5 <span>Mini</span>",
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
  try {
    await store.setModel(model.id);
  } catch {
    // DB save failed — rollback UI to previous selection.
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
}

/* === Чат === */
const messageText = ref("");
const chatMessages = ref<ChatMessage[]>(
  store.chatHistoryPrefetchOk ? [...store.chatHistory] : [],
);
const editableDiv = ref<HTMLElement | null>(null);
const chatContent = ref<HTMLElement | null>(null);

const isStreaming = computed(() => streamingBotIdx.value !== -1);
const isSubmitDisabled = computed(
  () => messageText.value.trim() === "" || isStreaming.value,
);

/**
 * Maps req_id → chatMessages index for bot responses initiated on ANOTHER device.
 * Used by multi-device type handlers to update the correct message slot.
 */
const remoteBotSlots = new Map<string, number>();

function onInput(e: Event) {
  messageText.value = (e.target as HTMLElement).innerText;
}

/**
 * Paste only plain text into contenteditable.
 * Uses Selection API (not deprecated execCommand) — works on iOS, Android, desktop.
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
}

function scrollToBottom() {
  // Hide the scroll button immediately — this is a programmatic autoscroll.
  showScrollBtn.value = false;
  isNearBottom.value = true;
  suppressScrollEvents = true;
  // requestAnimationFrame fires after layout is computed — more reliable than nextTick for scroll.
  requestAnimationFrame(() => {
    const el = chatContent.value;
    if (!el) {
      suppressScrollEvents = false;
      return;
    }
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

/** Smooth scroll to bottom — used by the scroll-to-bottom button. */
function scrollToBottomSmooth() {
  showScrollBtn.value = false;
  isNearBottom.value = true;
  suppressScrollEvents = true;
  const el = chatContent.value;
  if (!el) {
    suppressScrollEvents = false;
    return;
  }
  el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  // Keep button hidden during smooth scroll, then recalculate state when done
  setTimeout(() => {
    suppressScrollEvents = false;
  }, 600);
}

/** Scroll to bottom only when the user is already near the bottom. */
function scrollToBottomIfAtBottom() {
  if (isNearBottom.value) scrollToBottom();
}

/** Chat scroll event — tracks isNearBottom + triggers lazy-load when near top. */
function onChatScroll() {
  if (suppressScrollEvents) return;
  const el = chatContent.value;
  if (!el) return;
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
  isNearBottom.value = distFromBottom < 150;
  showScrollBtn.value = distFromBottom > 100;
}

/* === Загрузка истории из API === */
function applyChatHistory(messages: ChatMessage[]) {
  chatMessages.value = messages;
  store.setChatHistory(messages);
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
    cursorIdx.value = next_before_index;
    // Backend is the single source of truth for whether more pages exist.
    hasMoreToLoad.value = has_more;
    hasLoadedOlderPages.value = true;
    // Restore scroll: keep the same visual position (stable viewport after prepend).
    await nextTick();
    if (el) el.scrollTop = prevScrollTop + (el.scrollHeight - prevScrollHeight);
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      // HTTP/2 session teardown during WS reconnect — retry automatically after it settles.
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
  // Never overwrite an active stream — the spinner slots would be lost.
  if (streamingBotIdx.value !== -1) return;
  // If user has manually loaded older pages, skip reconnect refresh to preserve them.
  if (hasLoadedOlderPages.value && !forceScroll) return;
  // Deduplicate: set flag immediately (before any await) to prevent concurrent calls.
  if (isLoadingHistory) return;
  isLoadingHistory = true;

  try {
    // Уже подгружено на экране загрузки — не дублируем запросы (меньше abort / HTTP2).
    if (store.chatHistoryPrefetchOk && store.dialogId) {
      applyChatHistory([...store.chatHistory]);
      cursorIdx.value = store.chatHistoryNextCursor;
      hasMoreToLoad.value = store.chatHistoryNextCursor > 0;
      if (forceScroll) {
        await nextTick();
        scrollToBottom();
      }
      return;
    }

    // Show cached messages immediately so the user sees content right away.
    const hadCachedData = store.chatHistory.length > 0;
    if (hadCachedData) {
      applyChatHistory([...store.chatHistory]);
      if (forceScroll) {
        await nextTick();
        scrollToBottom();
      }
    }

    const { dialog_id, messages, next_before_index } =
      await api.bootstrapDialog();
    store.setDialogId(dialog_id);
    // Re-check: a stream may have started while bootstrapDialog was in-flight.
    if (streamingBotIdx.value === -1) {
      applyChatHistory(dialogMessagesToChat(messages ?? []));
      cursorIdx.value = next_before_index;
      hasMoreToLoad.value = next_before_index > 0;
      // Always go to bottom after API refresh — position saving removed.
      // The ResizeObserver fix ensures no 10px jump from footer height changes.
      await nextTick();
      const el = chatContent.value;
      if (el) {
        showScrollBtn.value = false;
        isNearBottom.value = true;
        suppressScrollEvents = true;
        requestAnimationFrame(() => {
          el.scrollTop = el.scrollHeight;
          suppressScrollEvents = false;
          // Recalculate button state after programmatic scroll
          setTimeout(() => onChatScroll(), 0);
        });
      }
    }
  } catch (e: unknown) {
    // AbortError is normal (tab navigation/close) — don't log it as an error.
    if (e instanceof DOMException && e.name === "AbortError") return;
    console.error("Ошибка при загрузке истории чата:", e);
  } finally {
    isLoadingHistory = false;
  }
}

/* === Новый диалог === */
async function clearCurrentChat() {
  // Clear UI immediately — don't wait for API round-trip
  chatMessages.value = [];
  showScrollBtn.value = false;
  isNearBottom.value = true;
  store.clearChatHistory();
  cursorIdx.value = 0;
  hasLoadedOlderPages.value = false;
  hasMoreToLoad.value = false;
  sidebarActive.value = false;
  setTimeout(() => {
    sidebarDisplay.value = false;
  }, 200);
  try {
    const { dialog_id } = await api.newDialog();
    store.setDialogId(dialog_id);
  } catch (e) {
    console.error("Ошибка при создании нового диалога:", e);
  }
}

/* === Отправка сообщения === */
async function sendMessage() {
  if (isStreaming.value) return;
  const text = messageText.value.trim();
  if (!text) return;

  // Собираем последние 10 пар user/bot для контекста (только текстовые)
  const pairs: { user: string; bot: string }[] = [];
  for (let i = 0; i + 1 < chatMessages.value.length; i += 2) {
    const u = chatMessages.value[i];
    const b = chatMessages.value[i + 1];
    if (u?.type === "user" && b?.type === "bot" && b.contentType !== "image") {
      pairs.push({ user: u.text, bot: b.text });
    }
  }
  const dialogMessages = pairs.slice(-10);

  chatMessages.value.push({ text, type: "user" });
  messageText.value = "";
  if (editableDiv.value) editableDiv.value.innerText = "";

  await nextTick();
  scrollToBottom();

  const isImageModel = currentModelId.value === "gpt-image-1.5";
  chatMessages.value.push({ type: "bot", contentType: "text", text: "" });
  const botIdx = chatMessages.value.length - 1;
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

  try {
    if (isImageModel) {
      // Image generation over WebSocket: progress events → no polling, no HTTP/2 PING issue.
      const result = await wsClient.generateImage(text, store.dialogId, () => {
        // Keep the empty bot slot (spinner) during both moderation and generation.
      });
      if (result.dialog_id) store.setDialogId(result.dialog_id);
      const imageUrl = result.url ?? "";
      chatMessages.value[botIdx] = {
        type: "bot",
        contentType: "image",
        imageUrl,
        text: "",
      };
    } else {
      // Text chat via WebSocket token stream.
      const result = await wsClient.chatStream({
        message: text,
        dialog_id: store.dialogId ?? undefined,
        dialog_messages: dialogMessages,
        model: currentModelId.value,
        chat_mode: store.user?.mini_app_chat_mode ?? "mini_app_assistant",
      });
      if (result.dialog_id) store.setDialogId(result.dialog_id);
      if (result.is_flagged) {
        chatMessages.value[botIdx] = {
          type: "bot",
          contentType: "text",
          text: t("message_flagged"),
        };
      } else {
        chatMessages.value[botIdx] = {
          type: "bot",
          contentType: "text",
          text: result.answer,
        };
      }
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    const reqId = (e as { reqId?: string }).reqId;
    if (msg === "network error" && reqId) {
      // WS dropped mid-generation (text or image) — keep the spinner and wait for reconnect.
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

  if (!pendingReconnectReqId.value) streamingBotIdx.value = -1;
  if (generationWatchdog) {
    clearInterval(generationWatchdog);
    generationWatchdog = null;
  }
  await nextTick();
  scrollToBottom(); // always scroll after own message receives a response
  store.setChatHistory(chatMessages.value);
}

function formatMessage(text: string): string {
  return text.replace(/\n/g, "<br>");
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

function onReaction(
  index: number,
  reaction: "like" | "dislike",
  userMsg: string,
  botMsg: string,
) {
  if (reactionMap.get(index) === reaction) {
    reactionMap.delete(index); // toggle off — снять реакцию
    return;
  }
  reactionMap.set(index, reaction);
  api
    .sendReaction({
      reaction,
      model: currentModelId.value,
      user_message: userMsg,
      bot_message: botMsg,
    })
    .catch((err) => console.warn("[reaction]", err));
}

/**
 * Universal file save — cascade of 4 strategies:
 * 1. showSaveFilePicker  → native "Save As" dialog (Chromium desktop / tdesktop)
 * 2a. navigator.share({files}) → system share sheet (iOS, Android, macOS)
 *     – canShare() guard removed: it returns false on Android even when share works
 * 2b. navigator.share({text}) → text-only share fallback for TXT on Android
 * 3. window.open(_blank)  → opens blob in browser tab; escapes iframe sandbox (Telegram Web)
 * 4. a.download           → traditional auto-download (emergency fallback)
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
 *   1. showSaveFilePicker — native “Save As” dialog (Chromium: tdesktop, Chrome desktop)
 *   2. navigator.share({files}) — system share sheet (iOS, Android, macOS, Chrome Win/Mac)
 *   3. navigator.share({text}) — text-only fallback for TXT when file share is unavailable
 *   4. a.download — last resort (tdesktop fallback, some Android WebViews)
 *
 * window.open(blob) is intentionally NOT used — opens a raw blob URL in browser, which
 * is meaningless on macOS/Android and confusing everywhere else.
 * AbortError (user dismissed) always stops the cascade immediately.
 */
async function saveBlob(
  blob: Blob,
  filename: string,
  pickerTypes: { description: string; accept: Record<string, string[]> }[],
  /** Plain text — enables share({text}) fallback for TXT */
  plainText?: string,
): Promise<void> {
  // ── 1. Save As dialog (Chromium desktop, tdesktop)
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
      // SecurityError (sandboxed iframe) or NotAllowedError (no gesture) — fall through
    }
  }

  // ── 2. Web Share API with files (iOS, Android, macOS, Chrome on Windows/macOS) ─────
  // No canShare() guard — it returns false on some Android WebViews even when
  // navigator.share({files}) actually succeeds.
  if (typeof navigator.share === "function") {
    const file = new File([blob], filename, { type: blob.type });
    try {
      await navigator.share({ files: [file] });
      return;
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") return;
      // TypeError / NotAllowedError: file sharing not supported — try text
    }

    // ── 3. Text-only share — TXT fallback (Android when file share unavailable) ───
    if (plainText) {
      try {
        await navigator.share({ title: filename, text: plainText });
        return;
      } catch (err: unknown) {
        if ((err as Error)?.name === "AbortError") return;
      }
    }
  }

  // ── 4. a.download — last resort
  // Works in tdesktop (shows Downloads panel), some Android WebViews.
  // Blocked in sandboxed iframes (Telegram Web in browser) — acceptable
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

  // Render plain text via hidden div — all Unicode works, no HTML tags
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

function copyToClipboard(text: string, index: number) {
  const plain = stripHtml(text);

  const finish = (ok: boolean) => {
    // Clear any text selection left by iOS touch
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
  };

  if (navigator.clipboard?.writeText) {
    navigator.clipboard
      .writeText(plain)
      .then(() => finish(true))
      .catch(() => {
        // iOS fallback: execCommand
        const ta = document.createElement("textarea");
        ta.value = plain;
        ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        window.getSelection()?.removeAllRanges();
        finish(ok);
      });
  } else {
    // No Clipboard API at all
    const ta = document.createElement("textarea");
    ta.value = plain;
    ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    finish(ok);
  }
}

/* === Случайная обезьянка для пустого чата === */
const emptyCardImage = ref("");

let footerResizeObs: ResizeObserver | null = null;

// iOS: touch-triggered tooltip — briefly shows tooltip on tap, then removes it
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
  // Remove after 700ms — enough to read, gone before next interaction
  tipActiveTimer = setTimeout(() => {
    wrap.classList.remove("tip-active");
    tipActiveTimer = null;
  }, 700);
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
  }

  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("touchstart", handleTipTouch, { passive: true });

  // Proactively open WebSocket so the first message feels instant.
  wsClient.connect().catch(() => {});

  // ── Multi-device sync: type handlers
  // These fire when a broadcast arrives from ANOTHER device (no matching id-handler).

  // Another device sent a user message → add it + an empty bot slot.
  wsClient.setTypeHandler("user_message", (msg) => {
    const text = (msg.text as string) ?? "";
    if (!text) return;
    // Ensure prior history is visible before appending the new stream slot.
    if (!chatMessages.value.length && store.chatHistory.length) {
      chatMessages.value = [...store.chatHistory];
    }
    chatMessages.value.push({ text, type: "user" });
    chatMessages.value.push({ type: "bot", contentType: "text", text: "" });
    const botIdx = chatMessages.value.length - 1;
    remoteBotSlots.set(msg.id as string, botIdx);
    streamingBotIdx.value = botIdx;
    nextTick().then(scrollToBottomIfAtBottom);
  });

  // Generation is starting on another device → show loading state.
  wsClient.setTypeHandler("generation_start", (msg) => {
    const botIdx = remoteBotSlots.get(msg.id as string);
    if (botIdx !== undefined) {
      // Slot was created by user_message handler — just ensure streaming is marked.
      streamingBotIdx.value = botIdx;
    }
  });

  // Token chunk from another device's generation — no longer sent (no streaming).
  // Handler kept as no-op so connection_ack slots are not broken on old server.
  wsClient.setTypeHandler("chat_token", () => {});

  // Another device's chat finished.
  wsClient.setTypeHandler("chat_done", (msg) => {
    const id = msg.id as string;
    const botIdx = remoteBotSlots.get(id);
    remoteBotSlots.delete(id);
    streamingBotIdx.value = -1;
    if (botIdx !== undefined) {
      const isFlagged = (msg.is_flagged as boolean) ?? false;
      chatMessages.value[botIdx] = {
        type: "bot",
        contentType: "text",
        text: isFlagged ? t("message_flagged") : ((msg.answer as string) ?? ""),
      };
    }
    if (msg.dialog_id) store.setDialogId(msg.dialog_id as string);
    store.setChatHistory(chatMessages.value);
    nextTick().then(scrollToBottomIfAtBottom);
  });

  // Another device's chat errored.
  wsClient.setTypeHandler("chat_error", (msg) => {
    const id = msg.id as string;
    const botIdx = remoteBotSlots.get(id);
    remoteBotSlots.delete(id);
    streamingBotIdx.value = -1;
    if (botIdx !== undefined) {
      chatMessages.value[botIdx] = {
        type: "bot",
        contentType: "text",
        text:
          t("error_response") + ": " + ((msg.error as string) || "chat error"),
      };
    }
    store.setChatHistory(chatMessages.value);
  });

  // Another device's image progress — keep spinner (no text change).
  wsClient.setTypeHandler("image_progress", () => {});

  // Another device's image finished.
  wsClient.setTypeHandler("image_done", (msg) => {
    const id = msg.id as string;
    const botIdx = remoteBotSlots.get(id);
    remoteBotSlots.delete(id);
    streamingBotIdx.value = -1;
    if (botIdx !== undefined) {
      const rawUrl = (msg.url as string) ?? "";
      const imageUrl = rawUrl.startsWith("/") ? `${BASE_URL}${rawUrl}` : rawUrl;
      chatMessages.value[botIdx] = {
        type: "bot",
        contentType: "image",
        imageUrl,
        text: "",
      };
    }
    if (msg.dialog_id) store.setDialogId(msg.dialog_id as string);
    store.setChatHistory(chatMessages.value);
    nextTick().then(scrollToBottomIfAtBottom);
  });

  // Another device's image errored.
  wsClient.setTypeHandler("image_error", (msg) => {
    const id = msg.id as string;
    const botIdx = remoteBotSlots.get(id);
    remoteBotSlots.delete(id);
    streamingBotIdx.value = -1;
    if (botIdx !== undefined) {
      chatMessages.value[botIdx] = {
        type: "bot",
        contentType: "text",
        text:
          t("error_response") + ": " + ((msg.error as string) || "image error"),
      };
    }
    store.setChatHistory(chatMessages.value);
  });

  // Connection lost (WebSocket closed) — reset streaming state.
  wsClient.setTypeHandler("connection_lost", () => {
    remoteBotSlots.clear();
    streamingBotIdx.value = -1;
  });

  // Connected while a generation is already running on another device.
  // Push the original user message + empty bot slot so the spinner shows
  // and incoming chat_token / image_progress frames have somewhere to land.
  wsClient.setTypeHandler("connection_ack", async (msg) => {
    const genId = msg.generating_id as string | undefined;
    if (msg.is_generating) {
      if (genId && genId === pendingReconnectReqId.value) {
        // Our own image generation survived the disconnect — restore the spinner slot.
        remoteBotSlots.set(genId, pendingReconnectBotIdx.value);
        streamingBotIdx.value = pendingReconnectBotIdx.value;
        pendingReconnectReqId.value = null;
        pendingReconnectBotIdx.value = -1;
      } else if (streamingBotIdx.value === -1) {
        // Another device's generation — check for an existing slot first.
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
          // Reuse the existing bot slot — just restore streaming state.
          if (genId) remoteBotSlots.set(genId, n - 1);
          streamingBotIdx.value = n - 1;
        } else {
          // First time seeing this generation — show prior history, then add slot.
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
      //   A) Image was generated and saved to DB while WS was down → show from history.
      //   B) Generation failed / never reached server        → auto-retry the request.
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
          // User had loaded older messages — preserve them.
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
          : true; // no prompt captured → don't retry
        if (!responseArrived && savedText) {
          // Generation was lost (not in DB) — re-submit the request automatically.
          messageText.value = savedText;
          if (editableDiv.value) editableDiv.value.innerText = savedText;
          sendMessage();
        }
      } catch {
        // Network error during bootstrap — use loadChatHistory WITHOUT forceScroll so
        // hasLoadedOlderPages guard is respected (older messages are preserved).
        loadChatHistory();
      }
    } else if (initialLoadDone.value) {
      // Reconnected while idle — refresh history to pick up messages from other devices.
      store.chatHistoryPrefetchOk = false;
      loadChatHistory();
    }
  });

  if (store.chatHistoryPrefetchOk) {
    await loadChatHistory(true);
    initialLoadDone.value = true;
    return;
  }

  await loadChatHistory(true);
  initialLoadDone.value = true;
  // scrollToBottom is now handled inside loadChatHistory based on position.
});

let wasOnChat = false;

onActivated(() => {
  // On return from Settings, always jump to latest messages.
  if (!wasOnChat) return;
  isReturningFromSettings.value = true;
  // Apply bottom state immediately to avoid one-frame flash of old scroll/button state.
  showScrollBtn.value = false;
  isNearBottom.value = true;
  jumpToBottomSilent();
  nextTick(() => {
    jumpToBottomSilent();
    // Release the guard only after DOM/layout settles on the restored bottom state.
    requestAnimationFrame(() => {
      isReturningFromSettings.value = false;
    });
  });
});

onDeactivated(() => {
  wasOnChat = true;
  // Hide cached scroll button before KeepAlive stores the inactive DOM snapshot.
  showScrollBtn.value = false;
  isReturningFromSettings.value = true;
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleDocumentClick);
  document.removeEventListener("touchstart", handleTipTouch);
  if (tipActiveTimer) clearTimeout(tipActiveTimer);
  document.body.style.overflow = "auto";
  if (copyTimeout) clearTimeout(copyTimeout);
  footerResizeObs?.disconnect();
  // Remove type handlers so they don't fire after the component is gone.
  for (const type of [
    "user_message",
    "generation_start",
    "chat_token",
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

/* Skeleton shimmer shown while the WebP image is loading */
.image-skeleton {
  width: 90%;
  max-width: 280px;
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  background: linear-gradient(
    90deg,
    var(--tg-theme-secondary-bg-color, #e0e0e0) 25%,
    var(--tg-theme-bg-color, #f5f5f5) 50%,
    var(--tg-theme-secondary-bg-color, #e0e0e0) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.4s ease-in-out infinite;
}

@keyframes skeleton-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* Hide img tag while skeleton is visible to avoid flash of broken icon */
.image-loading {
  display: none;
}

.generated-image {
  max-width: 90%;
  border-radius: 8px;
  max-height: 40vh; /* ограничение высоты */
  object-fit: contain;
  cursor: pointer; /* Указатель при наведении */
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

/* Адаптивность для мобильных устройств */
@media (max-width: 768px) {
  .generated-image {
    max-width: 95%;
    max-height: 35vh;
  }
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
     first frame — prevents the brief "square" rendering artifact on Android. */
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

/* Bottom spacer — replaces padding-bottom on .chat-content.
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
</style>
