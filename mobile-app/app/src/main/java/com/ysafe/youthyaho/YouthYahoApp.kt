package com.ysafe.youthyaho

import android.app.Application

class YouthYahoApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
