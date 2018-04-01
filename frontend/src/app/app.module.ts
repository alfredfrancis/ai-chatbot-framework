import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';



/* Material UI imports begins here */
import {BrowserAnimationsModule} from '@angular/platform-browser/animations';
/* Material UI imports ends here */


/* Project Components imports begins here */
import { DashboardModule } from './dashboard/dashboard.module';
/* Project Components imports ends here */


@NgModule({
  declarations: [
    AppComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    BrowserAnimationsModule,
    DashboardModule,
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
