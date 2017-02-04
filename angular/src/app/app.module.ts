import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpModule } from '@angular/http';

import { AppComponent } from './app.component';
import { TracebacksComponent } from './tracebacks/tracebacks.component';
import { TracebackService } from './tracebacks/traceback.service';

@NgModule({
  declarations: [
    AppComponent,
    TracebacksComponent
  ],
  imports: [
    BrowserModule,
    FormsModule,
    HttpModule
  ],
  providers: [ TracebackService ],
  bootstrap: [AppComponent]
})
export class AppModule { }
