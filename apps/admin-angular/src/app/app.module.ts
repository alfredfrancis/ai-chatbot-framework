import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { AppComponent } from './app.component';
import {BrowserAnimationsModule} from '@angular/platform-browser/animations';
import { StoryModule } from './story/story.module';
import { RouterModule } from '@angular/router';
import { MatToolbarModule, MatIconModule } from '@angular/material';
import { HttpModule } from '@angular/http';

@NgModule({
  declarations: [
    AppComponent
  ],
  imports: [
    BrowserModule,
    RouterModule,
    HttpModule,
    MatToolbarModule, MatIconModule,
    BrowserAnimationsModule,
    StoryModule
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
